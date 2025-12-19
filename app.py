import json
import requests
from flask import jsonify, request, make_response
from flask_migrate import Migrate
from dbms import app, db
from geoid_list.geoid_list import list_bp
from s2_service import S2Service
from utils import Utils
from dotenv import load_dotenv
from shapely.geometry import Point
from shapely.wkt import loads as load_wkt
from flask_wtf.csrf import generate_csrf
from localStoragePy import localStoragePy
import regionlist_id.regionListId as region_service
import regionlist_id.fieldListId as field_service
from flask import Flask, render_template, jsonify, request, url_for, session

load_dotenv()
localStorage = localStoragePy('asset-registry', 'text')

from dbms.models import geoIdsModel, s2CellTokensModel, cellsGeosMiddleModel

migrate = Migrate(app, db)
app.register_blueprint(list_bp)  # url_prefix='/geoid-lists'


@app.route('/', methods=["GET"])
@Utils.fetch_token
def index(token, refresh_token):
    """
    Endpoint to receive tokens from user-registry and return a response
    """
    try:
        to_return = {'access_token': token, 'refresh_token': refresh_token}
        localStorage.setItem('access_token', token)
        localStorage.setItem('refresh_token', refresh_token)
        return jsonify(to_return)
    except Exception as e:
        return jsonify({
            'message': 'Asset Registry Error',
            'error': f'{e}'
        }), 400


@app.route('/logout', methods=['GET'])
@Utils.token_required
def logout():
    try:
        refresh_token = Utils.get_bearer_token()
        if not refresh_token:
            return jsonify({
                'message': 'Asset Registry Logout Error',
                'error': 'No token.'
            }), 400
        tokens = {'Authorization': 'Bearer' + refresh_token, 'X-FROM-ASSET-REGISTRY': "True"}
        requests.get(app.config['USER_REGISTRY_BASE_URL'] + '/logout', headers=tokens)
        resp_fe = make_response(jsonify({"message": "Successfully logged out"}), 200)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        resp_fe.set_cookie('access_token_cookie', '', expires=0)
        resp_fe.set_cookie('refresh_token_cookie', '', expires=0)
        return resp_fe
    except Exception as e:
        return jsonify({
            'message': 'Asset Registry Logout Error',
            'error': f'{e}'
        }), 400


# @app.route('/login', methods=['POST'])
# def login():
#     if request.is_json:
#         data = request.get_json()
#         email = data.get('email')
#         password = data.get('password')
#         if email is None or password is None:
#             return jsonify({'message': 'Missing arguments'}), 400
#         data['asset_registry'] = True
#         try:
#             headers = {'X-EMAIL': email, 'X-PASSWORD': password, 'X-ASSET-REGISTRY': "True"}
#             res = requests.get(app.config['USER_REGISTRY_BASE_URL'], headers=headers)
#             json_res = json.loads(res.content.decode())
#         except Exception as e:
#             return jsonify({
#                 'message': 'User Registry Error',
#                 'error': f'{e}'
#             }), 400
#         if res.status_code == 200:
#             response_fe = make_response(jsonify(json_res), 200)
#             response_fe.set_cookie('refresh_token_cookie', json_res.get('refresh_token'))
#             response_fe.set_cookie('access_token_cookie', json_res.get('access_token'))
#             return response_fe
#         else:
#             response_fe = make_response(jsonify(json_res), 400)
#             return response_fe
#     return jsonify({'message': 'Missing JSON in request'}), 400

@app.route('/login', methods=['POST'])
def login():
    if request.is_json:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        if email is None or password is None:
            return jsonify({'message': 'Missing arguments'}), 400
        try:
            headers = {'X-EMAIL': email, 'X-PASSWORD': password, 'X-ASSET-REGISTRY': "True"}
            res = requests.get(app.config['USER_REGISTRY_BASE_URL'], headers=headers)
            json_res = json.loads(res.content.decode())
        except Exception as e:
            return jsonify({'message': 'User Registry Error', 'error': str(e)}), 400
        return jsonify(json_res), res.status_code
    return jsonify({'message': 'Missing JSON in request'}), 400

# @app.route('/kml-to-wkt', methods=['POST'])
# def convert_kml_to_wkt():
#     kml_file = request.files.get('kml')
#
#     fiona.supported_drivers['KML'] = 'rw'
#     f = fiona.BytesCollection(bytes(kml_file.content))
#     df = gpd.GeoDataFrame()
#
#     gdf = gpd.read_file(kml_file, driver='KML')
#     poly = gdf.geometry.iloc[0]  # shapely polygon
#     wkt = poly.wkt

# working returning only the geoid and s2 indices if return_s2_indices True
@app.route('/register-field-boundary', methods=['POST'])
@Utils.token_required_
def register_field_boundary(current_user_id):
    try:
        data = json.loads(request.data.decode('utf-8'))
        field_wkt = data.get('wkt')
        threshold = data.get('threshold') or 95
        resolution_level = 20
        return_s2_indices = bool(data.get('return_s2_indices', False))

        boundary_type = "manual"
        if request.headers.get('AUTOMATED-FIELD') is not None:
            automated_field = bool(int(request.headers.get('AUTOMATED-FIELD')))
            if automated_field:
                boundary_type = "automated"

        field_boundary_geo_json = Utils.get_geo_json(field_wkt)
        lat = field_boundary_geo_json['geometry']['coordinates'][0][0][1]
        lng = field_boundary_geo_json['geometry']['coordinates'][0][0][0]
        p = Point([lng, lat])
        country = Utils.get_country_from_point(p)
        are_in_acres = Utils.get_are_in_acres(field_wkt)

        if are_in_acres > 1000:
            return jsonify({
                "message": "Cannot register a field with Area greater than 1000 acres"
            }), 200

        # Generate Geo IDs
        indices = {
            13: S2Service.wkt_to_cell_tokens(field_wkt, 13),
            20: S2Service.wkt_to_cell_tokens(field_wkt, 20)
        }

        geo_id = Utils.generate_geo_id(indices[13])
        geo_id_l20 = Utils.generate_geo_id(indices[20])
        geo_id_exists_wkt = Utils.lookup_geo_ids(geo_id)

        # --- NEW FIELD REGISTRATION ---
        if not geo_id_exists_wkt:
            if return_s2_indices:
                indices.update({
                    8: S2Service.wkt_to_cell_tokens(field_wkt, 8),
                    15: S2Service.wkt_to_cell_tokens(field_wkt, 15),
                    18: S2Service.wkt_to_cell_tokens(field_wkt, 18),
                    19: S2Service.wkt_to_cell_tokens(field_wkt, 19),
                })
            records_list_s2_cell_tokens_middle_table_dict = Utils.records_s2_cell_tokens(indices)

            geo_data = Utils.register_field_boundary(
                current_user_id, geo_id, indices,
                records_list_s2_cell_tokens_middle_table_dict,
                field_wkt, country, boundary_type
            )

            response = {
                "Geo Id": geo_id,
                "message": "Field Boundary registered successfully."
            }

            if return_s2_indices:
                s2_index = data.get('s2_index') or "8,13"
                print(f"s2_index======== {s2_index}")
                if s2_index:
                    s2_index_to_fetch = [int(i) for i in s2_index.split(',')]
                    s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)
                    if s2_indexes_to_remove != -1:
                        s2_data = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
                        if isinstance(s2_data, dict) and "wkt" in s2_data:
                            s2_data.pop("wkt")
                        response["S2 Cell Tokens"] = s2_data

            return jsonify(response), 200

        # --- EXISTING GEO ID HANDLING ---
        s2_index_to_check = indices[20]
        matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index_to_check, "")
        percentage_matched_geo_ids = Utils.check_percentage_match(
            matched_geo_ids, s2_index_to_check, resolution_level, threshold
        )

        if len(percentage_matched_geo_ids) > 0:
            return jsonify({
                #"message": "Threshold matched for already registered Field Boundary(ies)",
                "message": "field already registered previously",
                "matched geo ids": percentage_matched_geo_ids
            }), 400

        geo_id_exists_wkt_l20 = Utils.lookup_geo_ids(geo_id_l20)
        if not geo_id_exists_wkt_l20:
            if return_s2_indices:
                indices.update({
                    8: S2Service.wkt_to_cell_tokens(field_wkt, 8),
                    15: S2Service.wkt_to_cell_tokens(field_wkt, 15),
                    18: S2Service.wkt_to_cell_tokens(field_wkt, 18),
                    19: S2Service.wkt_to_cell_tokens(field_wkt, 19),
                })
            records_list_s2_cell_tokens_middle_table_dict = Utils.records_s2_cell_tokens(indices)

            geo_data = Utils.register_field_boundary(
                current_user_id, geo_id_l20, indices,
                records_list_s2_cell_tokens_middle_table_dict,
                field_wkt, country, boundary_type
            )

            response = {
                "Geo Id": geo_id_l20,
                "message": "Field Boundary registered successfully."
            }

            if return_s2_indices:
                s2_index = data.get('s2_index') or "8,13"
                if s2_index:
                    s2_index_to_fetch = [int(i) for i in s2_index.split(',')]
                    s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)
                    if s2_indexes_to_remove != -1:
                        s2_data = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
                        if isinstance(s2_data, dict) and "wkt" in s2_data:
                            s2_data.pop("wkt")
                        response["S2 Cell Tokens"] = s2_data

            return jsonify(response), 200

        # --- Already Registered ---
        return jsonify({
            "message": "Field Boundary already registered.",
            "Geo Id": geo_id_l20
        }), 200

    except Exception as e:
        return jsonify({
            "message": "Register Field Boundary Error",
            "error": str(e)
        }), 400


@app.route('/register-field-boundaries-geojson', methods=['POST'])
@Utils.token_required_
def register_field_boundaries_geojson(current_user_id):
    """
    Bulk registration of multiple field boundaries from GeoJSON FeatureCollection
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        if 'type' not in data or data['type'] != 'FeatureCollection' or 'features' not in data:
            return jsonify({
                'message': 'Invalid GeoJSON FeatureCollection format'
            }), 400

        threshold = data.get('threshold', 95)
        resolution_level = 20
        results = []

        boundary_type = "manual"
        if request.headers.get('AUTOMATED-FIELD') is not None:
            automated_field = bool(int(request.headers.get('AUTOMATED-FIELD')))
            if automated_field:
                boundary_type = "automated"        

        for feature in data['features']:
            try:
                # Convert GeoJSON to WKT
                field_wkt = Utils.geojson_to_wkt(feature)
                field_boundary_geo_json = feature
                geometry_type = feature['geometry']['type']

                # set lat lng based on geometry type
                if geometry_type == 'Point':
                    lat = feature['geometry']['coordinates'][1]
                    lng = feature['geometry']['coordinates'][0]
                    indices = {
                        8: S2Service.wkt_to_cell_tokens(field_wkt, 8, point=True),
                        13: S2Service.wkt_to_cell_tokens(field_wkt, 13, point=True),
                        15: S2Service.wkt_to_cell_tokens(field_wkt, 15, point=True),
                        18: S2Service.wkt_to_cell_tokens(field_wkt, 18, point=True),
                        19: S2Service.wkt_to_cell_tokens(field_wkt, 19, point=True),
                        20: S2Service.wkt_to_cell_tokens(field_wkt, 20, point=True),
                        30: S2Service.wkt_to_cell_tokens(field_wkt, 30, point=True)
                    }
                else:  # Polygon
                    lat = feature['geometry']['coordinates'][0][0][1]
                    lng = feature['geometry']['coordinates'][0][0][0]
                    indices = {
                        8: S2Service.wkt_to_cell_tokens(field_wkt, 8),
                        13: S2Service.wkt_to_cell_tokens(field_wkt, 13),
                        15: S2Service.wkt_to_cell_tokens(field_wkt, 15),
                        18: S2Service.wkt_to_cell_tokens(field_wkt, 18),
                        19: S2Service.wkt_to_cell_tokens(field_wkt, 19),
                        20: S2Service.wkt_to_cell_tokens(field_wkt, 20)
                    }

                p = Point([lng, lat])
                country = Utils.get_country_from_point(p)
                print("Country:", country)

                # Skip area check for points
                if geometry_type != 'Point':
                    are_in_acres = Utils.get_are_in_acres(field_wkt)
                    if are_in_acres > 1000:
                        results.append({
                            "status": "skipped",
                            "message": f"Cannot register a field with Area greater than 1000 acres",
                            "field_area_acres": are_in_acres,
                            "geo_json": field_boundary_geo_json
                        })
                        continue

                s2_index = feature.get('properties', {}).get('s2_index')
                s2_indexes_to_remove = None
                if s2_index:
                    s2_index_to_fetch = [int(i) for i in s2_index.split(',')]
                    s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)

                # indices = {8: S2Service.wkt_to_cell_tokens(field_wkt, 8),
                #           13: S2Service.wkt_to_cell_tokens(field_wkt, 13),
                #           15: S2Service.wkt_to_cell_tokens(field_wkt, 15),
                #           18: S2Service.wkt_to_cell_tokens(field_wkt, 18),
                #           19: S2Service.wkt_to_cell_tokens(field_wkt, 19),
                #           20: S2Service.wkt_to_cell_tokens(field_wkt, 20)}

                records_list_s2_cell_tokens_middle_table_dict = Utils.records_s2_cell_tokens(indices)
                geo_id = Utils.generate_geo_id(indices[13])
                geo_id_l20 = Utils.generate_geo_id(indices[20])
                geo_id_exists_wkt = Utils.lookup_geo_ids(geo_id)
                if not geo_id_exists_wkt:
                    geo_data_to_return = None
                    geo_data = Utils.register_field_boundary(current_user_id , geo_id, indices, records_list_s2_cell_tokens_middle_table_dict,
                                                     field_wkt, country, boundary_type)
                    if s2_index and s2_indexes_to_remove != -1:
                        geo_data_to_return = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
                    
                    results.append({
                        "status": "created",
                        "message": "Field Boundary registered successfully",
                        "geo_id": geo_id,
                        "s2_cell_tokens": geo_data_to_return,
                        "geo_json": field_boundary_geo_json
                    })
                    continue

                s2_index_to_check = indices[20]
                matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index_to_check, "")
                percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index_to_check,
                                                                        resolution_level, threshold)
                
                if len(percentage_matched_geo_ids) > 0:
                    results.append({
                        "status": "exists",
                        "message": "Threshold matched for already registered Field Boundary(ies)",
                        "matched_geo_ids": percentage_matched_geo_ids,
                        "geo_json": field_boundary_geo_json
                    })
                    continue

                geo_id_exists_wkt_l20 = Utils.lookup_geo_ids(geo_id_l20)
                if not geo_id_exists_wkt_l20:
                    geo_data_to_return = None
                    geo_data = Utils.register_field_boundary(current_user_id,geo_id_l20, indices,
                                                           records_list_s2_cell_tokens_middle_table_dict,
                                                           field_wkt, country, boundary_type)
                    if s2_index and s2_indexes_to_remove != -1:
                        geo_data_to_return = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
                    
                    results.append({
                        "status": "created",
                        "message": "Field Boundary registered successfully",
                        "geo_id": geo_id_l20,
                        "s2_cell_tokens": geo_data_to_return,
                        "geo_json": field_boundary_geo_json
                    })
                else:
                    results.append({
                        "status": "exists",
                        "message": "Field Boundary already registered",
                        "geo_id": geo_id_l20,
                        "geo_json_requested": field_boundary_geo_json,
                        "geo_json_registered": Utils.get_geo_json(geo_id_exists_wkt_l20)
                    })

            except Exception as field_error:
                results.append({
                    "status": "error",
                    "message": str(field_error),
                    "geo_json": field_boundary_geo_json
                })

        return jsonify({
            "message": "Bulk registration completed",
            "results": results
        })

    except Exception as e:
        return jsonify({
            'message': 'Bulk Register Field Boundaries Error',
            'error': str(e)
        }), 400

@app.route('/register-point', methods=['POST'])
@Utils.token_required
def register_point():
    """
    Registering a point against a Geo Id
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        point_wkt = data.get('wkt')
        resolution_level = 30
        point_geo_json = Utils.get_geo_json(point_wkt)

        boundary_type = "manual"
        # check if request from automated system
        if request.headers.get('AUTOMATED-FIELD') is not None:
            automated_field = bool(int(request.headers.get('AUTOMATED-FIELD')))
            if automated_field:
                boundary_type = "automated"
        # set lat lng from geoJson first coordinate.
        lat = point_geo_json['geometry']['coordinates'][1]
        lng = point_geo_json['geometry']['coordinates'][0]
        p = Point([lng, lat])
        country = Utils.get_country_from_point(p)

        s2_index = data.get('s2_index')
        if s2_index:
            s2_index_to_fetch = [int(i) for i in (data.get('s2_index')).split(',')]
            s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)

        # get the Different resolution level indices
        # list against a key (e.g. 13) is a list of tokens(hex encoded version of the cell id)
        indices = {8: S2Service.wkt_to_cell_tokens(point_wkt, 8, point=True),
                   13: S2Service.wkt_to_cell_tokens(point_wkt, 13, point=True),
                   15: S2Service.wkt_to_cell_tokens(point_wkt, 15, point=True),
                   18: S2Service.wkt_to_cell_tokens(point_wkt, 18, point=True),
                   19: S2Service.wkt_to_cell_tokens(point_wkt, 19, point=True),
                   20: S2Service.wkt_to_cell_tokens(point_wkt, 20, point=True),
                   30: S2Service.wkt_to_cell_tokens(point_wkt, 30, point=True),
                   }

        # fetching the new s2 cell tokens records for different Resolution Levels, to be added in the database
        records_list_s2_cell_tokens_middle_table_dict = Utils.records_s2_cell_tokens(indices)
        # generate the geo_id only for `s2_index__l13_list`
        geo_id = Utils.generate_geo_id(indices[30])
        geo_id_l20 = Utils.generate_geo_id(indices[20])
        # lookup the database to see if geo id already exists
        geo_id_exists_wkt = Utils.lookup_geo_ids(geo_id)
        # if geo id not registered, register it in the database
        if not geo_id_exists_wkt:
            geo_data_to_return = None
            geo_data = Utils.register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_middle_table_dict,
                                                     point_wkt, country, boundary_type)
            if s2_index and s2_indexes_to_remove != -1:
                geo_data_to_return = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
            return jsonify({
                "message": "Point registered successfully.",
                "Geo Id": geo_id,
                "S2 Cell Tokens": geo_data_to_return,
                "Geo JSON": point_geo_json
            })
        else:
            return make_response(jsonify({
                "message": f"Point already registered.",
                "Geo Id": geo_id_l20,
                "Geo JSON requested": point_geo_json,
                "Geo JSON registered": Utils.get_geo_json(geo_id_exists_wkt)
            }), 400)
    except Exception as e:
        # noinspection PyPackageRequirements
        return jsonify({
            'message': 'Register Point Error',
            'error': f'{e}'
        }), 400


# Deprecated!!!
# @app.route('/fetch-overlapping-fields', methods=['POST'])
# @Utils.token_required
# def fetch_overlapping_fields():
#     """
#     Fetch the overlapping fields for a certain threshold
#     Overlap is being checked for L13 Resolution Level
#     Optional domain parameter for filtering fields based on associated domain
#     Returning the fields Geo Ids
#     """
#     try:
#         data = json.loads(request.data.decode('utf-8'))
#         field_wkt = data.get('wkt')
#         resolution_level = data.get('resolution_level') or 13
#         threshold = data.get('threshold') or 95
#         s2_index = data.get('s2_index')
#         domain = data.get('domain') or ""
#         boundary_type = data.get('boundary_type') or ""
#
#         # get the L13 indices
#         # s2_index__L13_list is a list of tokens(hex encoded version of the cell id)
#         s2_index__l13_list = S2Service.wkt_to_cell_tokens(field_wkt, resolution_level)
#
#         # fetch geo ids for tokens and checking for the percentage match
#         matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index__l13_list, domain, boundary_type)
#         percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index__l13_list, resolution_level,
#                                                                   threshold)
#         percentage_matched_fields = Utils.fetch_fields_for_geo_ids(percentage_matched_geo_ids, s2_index)
#
#         return make_response(jsonify({
#             "message": "The field Geo Ids with percentage match of the given threshold.",
#             "Matched Fields": percentage_matched_fields
#         }), 200)
#     except Exception as e:
#         return jsonify({
#             'message': 'Fetch Overlapping Fields Error',
#             'error': f'{e}'
#         }), 400


@app.route('/fetch-field/<geo_id>', methods=['GET'])
def fetch_field(geo_id):
    """
    Fetch a Field (S2 cell tokens) for the provided Geo Id
    :param geo_id:
    :return:
    """
    try:
        s2_index_to_fetch = None
        args = request.args
        if args.getlist('s2_index') and args.getlist('s2_index')[0]:
            s2_index_to_fetch = [int(i) for i in (args.getlist('s2_index')[0]).split(',')]
        if s2_index_to_fetch:
            s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)
        field = geoIdsModel.GeoIds.query \
            .filter_by(geo_id=geo_id) \
            .first()
        if not field:
            return make_response(jsonify({
                "message": "Field not found, invalid Geo Id."
            }), 404)
        field_boundary_geo_json = Utils.get_geo_json(json.loads(field.geo_data)['wkt'])
        geo_data = None
        if s2_index_to_fetch and s2_indexes_to_remove != -1:
            geo_data = Utils.get_specific_s2_index_geo_data(field.geo_data, s2_indexes_to_remove)
        return make_response(jsonify({
            "message": "Field fetched successfully.",
            "GEO Id": geo_id,
            "Geo Data": geo_data,
            "Geo JSON": field_boundary_geo_json
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Field Error',
            'error': f'{e}'
        }), 400


@app.route('/fetch-field-wkt/<geo_id>', methods=['GET'])
def fetch_field_wkt(geo_id):
    """
    Fetch a Field WKT for the provided Geo Id
    :param geo_id:
    :return:
    """
    try:
        field = Utils.fetch_field_by_geoid(geo_id)
        return make_response(jsonify({
            "message": "WKT fetched successfully.",
            "GEO Id": geo_id,
            "WKT": json.loads(field.geo_data)['wkt']
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Field WKT Error',
            'error': f'{e}'
        }), 400


@app.route('/get-percentage-overlap-two-fields', methods=['POST'])
def get_percentage_overlap_two_fields():
    """
    Passed in 2 GeoIDs, determine what is the % overlap of the 2 fields
    :return:
    """
    try:
        try:
            data = json.loads(request.data.decode('utf-8'))
            geo_id_field_1 = data.get('geo_id_field_1')
            geo_id_field_2 = data.get('geo_id_field_2')
            if not geo_id_field_1 or not geo_id_field_2:
                return make_response(jsonify({
                    "message": "Two Geo Ids are required."
                }), 400)

            percentage_overlap = Utils.get_percentage_overlap_two_fields(geo_id_field_1, geo_id_field_2)
        except AttributeError as error:
            return make_response(jsonify({
                "message": str(error)
            }), 404)

        return make_response(jsonify({
            "Percentage Overlap": str(percentage_overlap) + ' %'
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Get Percentage Overlap two Fields Error',
            'error': f'{e}'
        }), 400


@app.route('/fetch-fields-for-a-point', methods=['POST'])
@Utils.token_required
def fetch_fields_for_a_point():
    """
    Fetch all the fields containing the point
    Latitude and Longitude provided
    Check for L13 and L20
    Two stage search
    Optional domain parameter for filtering fields based on associated domain
    :return:
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        lat = data.get('latitude')
        long = data.get('longitude')
        domain = data.get('domain')
        boundary_type = data.get('boundary_type')
        s2_index = data.get('s2_index')
        if not lat or not long:
            return make_response(jsonify({
                "message": "Latitude and Longitude are required."
            }), 400)
        s2_cell_token_13, s2_cell_token_20 = S2Service.get_cell_token_for_lat_long(lat, long)
        fetched_fields = Utils.fetch_fields_for_a_point_two_way(s2_cell_token_13, s2_cell_token_20, domain, s2_index,
                                                                boundary_type)
        return make_response(jsonify({
            "Fetched fields": fetched_fields
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Fields for a Point Error',
            'error': f'{e}'
        }), 400


# Deprecated!!!
# @app.route('/fetch-bounding-box-fields', methods=['POST'])
# @Utils.token_required
# def fetch_bounding_box_fields():
#     """
#     Fetch the fields intersecting the Bounding Box
#     4 vertices are provided
#     :return:
#     """
#     try:
#         data = json.loads(request.data.decode('utf-8'))
#         latitudes = list(map(float, data.get('latitudes').split(' ')))
#         longitudes = list(map(float, data.get('longitudes').split(' ')))
#         s2_index = data.get('s2_index')
#         if not latitudes or not longitudes:
#             return make_response(jsonify({
#                 "message": "Latitudes and Longitudes are required."
#             }), 400)
#         s2_cell_tokens_13 = S2Service.get_cell_tokens_for_bounding_box(latitudes, longitudes)
#         s2_cell_tokens_20 = S2Service.get_cell_tokens_for_bounding_box(latitudes, longitudes, 20)
#         fields = Utils.fetch_fields_for_cell_tokens(s2_cell_tokens_13, s2_cell_tokens_20, s2_index)
#         return make_response(jsonify({
#             "message": fields
#         }), 200)
#     except Exception as e:
#         return jsonify({
#             'message': 'Fetch Bounding Box Fields Error',
#             'error': f'{e}'
#         }), 400


@app.route("/domains", methods=['GET'])
def fetch_all_domains():
    """
    Fetching all the domains from the User Registry
    :return:
    """
    res = requests.get(app.config['USER_REGISTRY_BASE_URL'] + '/domains', timeout=2)
    return jsonify({
        "message": "All domains",
        "Domains": res.json()['Domains']
    }), 200


@app.route("/domains", methods=['POST'])
def authorize_a_domain():
    """
    Authorize a domain, will have an authority token
    :return:
    """
    data = json.loads(request.data.decode('utf-8'))
    domain = data.get('domain')
    if not domain:
        return make_response(jsonify({
            "message": "Domain is required."
        }), 400)
    req_body = {'domain': domain}
    res = requests.post(app.config['USER_REGISTRY_BASE_URL'] + '/domains', json=req_body, timeout=2)
    return jsonify({
        "message": res.json()["Message"]
    }), 200


@app.route('/fetch-registered-field-count', methods=['GET'])
@Utils.token_required
def fetch_registered_field_count():
    """
    Fetch a total registered field count
    :return:
    """
    try:
        count = geoIdsModel.GeoIds.query \
            .count()
        return make_response(jsonify({
            "message": "Total count fetched successfully.",
            "count": count,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch registered field count error!',
            'error': f'{e}'
        }), 400


@app.route('/fetch-field-count-by-month', methods=['GET'])
@Utils.token_required
def fetch_field_count_by_month():
    """
    Fetch Registered Field count by Month, last 12 month
    :return:
    """
    try:
        count = Utils.get_row_count_by_month()
        return make_response(jsonify({
            "message": "fetched Count By Month successfully.",
            "count": count,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch field counts by month error!',
            'error': f'{e}'
        }), 400


@app.route('/fetch-field-count-by-country', methods=['GET'])
@Utils.token_required
def fetch_field_count_by_country():
    """
    Fetch Registered Field count by Country
    :return:
    """
    try:
        count = Utils.get_row_count_by_country()
        return make_response(jsonify({
            "message": "Fetched count by country successfully.",
            "count": count,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch field counts by country error!',
            'error': f'{e}'
        }), 400


@app.route('/fetch-field-count-by-domain', methods=['GET'])
@Utils.token_required
def fetch_field_count_by_domains():
    """
    Fetch Fields count by the Domains(authorized)
    :return:
    """
    try:
        count_by_authority_tokens = Utils.get_fields_count_by_domain()
        authority_tokens = [count_by_authority_token['authority_token'] for count_by_authority_token in
                            count_by_authority_tokens]
        # getting the domains against the authority tokens from User Registry
        csrf_token = generate_csrf()
        headers = {'X-CSRFToken': csrf_token, 'Authority-Tokens': str(authority_tokens)}
        res = requests.get(app.config['USER_REGISTRY_BASE_URL'] + '/fields-count-by-domain', json=authority_tokens,
                           timeout=2, headers=headers)
        if res.json().get("error") is not None:
            return jsonify({
                'message': 'Fetch field counts by domain error',
                'error': f'{res.json()["error"]}'
            }), 400
        authority_token_dict = res.json()["authority_token_dict"]
        field_count_by_domain = [{'domain': authority_token_dict[count_by_authority_token["authority_token"]],
                                  'count': count_by_authority_token["count"]} for count_by_authority_token in
                                 count_by_authority_tokens]
        return make_response(jsonify({
            "message": "Fetched count by domains successfully.",
            "count": field_count_by_domain,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch field counts by domain error!',
            'error': f'{e}'
        }), 400


@app.route('/populate-country-in-geo-ids', methods=['POST'])
def populate_country_in_geo_ids():
    # Get all rows where country is empty or None
    rows = db.session.query(geoIdsModel.GeoIds).filter((geoIdsModel.GeoIds.country == '') | (
            geoIdsModel.GeoIds.country == None)).all()  # don't replace with is None
    print(rows)
    # Loop through each row and update the country column
    for row in rows:
        # Parse the geo_data JSON string and extract the WKT string
        json_data = json.loads(row.geo_data)
        wkt_string = json_data['wkt']
        polygon = load_wkt(wkt_string)
        p = Point(polygon.exterior.coords[0])
        country = Utils.get_country_from_point(p)
        # Update the row in the database with the new country value
        row.country = country
        db.session.commit()
    return jsonify({'message': 'Countries updated successfully'}), 200


@app.route('/fetch-session-cookies', methods=['GET'])
def fetch_session_cookies():
    """
    Fetch the Session Cookies from User Registry
    :return:
    """
    try:
        access_token = localStorage.getItem('access_token')
        refresh_token = localStorage.getItem('refresh_token')
        return make_response(jsonify({"access_token": access_token, "refresh_token": refresh_token}))
    except Exception as e:
        return jsonify({
            'message': 'Fetch Session Cookies Error!',
            'error': f'{e}'
        }), 400


@app.route('/fetch-field-centroid/<geo_id>', methods=['GET'])
def fetch_field_centroid(geo_id):
    """
    Fetch a Field Centroid for the provided Geo Id
    :param geo_id:
    :return:
    """
    try:
        field = Utils.fetch_field_by_geoid(geo_id)
        field_wkt = json.loads(field.geo_data)['wkt']
        if not field_wkt:
            return make_response(jsonify({
                "message": "Field WKT not found, fetch Field Centroid Error."
            }), 400)
        centroid = Utils.fetch_field_centroid_by_wkt(field_wkt)
        return make_response(jsonify({
            "message": "Centroid fetched successfully.",
            "Centroid": centroid,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Field Centroid Error',
            'error': f'{e}'
        }), 400

# ---------- regionlistid map/qr code Start -------------

# API 1: Create regionListID for a list of region_ids
@app.route('/create_regionlistID', methods=['POST'])
def route_create_regionlistID():
    # We call the function directly from the service file
    return region_service.create_regionlistID_for_regionIDs()

# API 2: Get region boundaries for a regionListID
@app.route('/get_region_boundaries/', methods=['GET'])
def route_get_boundaries():
    return region_service.get_boundaries_for_regionlistID()

# API 3: Map endpoint for GeoJSON geometries
@app.route('/map', methods=['GET'])
def route_map_page():
    return region_service.map_page()

# API 4: Generate QR code
@app.route('/qrcode', methods=['GET'])
def route_generate_qrcode():
    return region_service.generate_qrcode()

# ---------- regionlistid map/qr code Start -------------


# ---------- fieldlistid map/qr code Start -------------

@app.route('/login_fieldlistid', methods=['POST'])
def route_login():
    return field_service.login()

@app.route('/signup', methods=['POST'])
def route_signup():
    return field_service.signup()

@app.route('/verify-otp', methods=['POST'])
def route_verify_otp():
    return field_service.verify_otp()

@app.route("/ingest", methods=["POST"])
def route_ingest_geoids():
    return  field_service.ingest_geoids()

@app.route('/get_user_data', methods=['POST'])
def route_get_user_data():
    return field_service.get_user_data()

@app.route('/add-to-acl', methods=['POST'])
def route_add_to_acl():
    return field_service.add_to_acl()

@app.route('/request-otp-fieldlistid', methods=['POST'])
def route_request_otp_fieldlistid():
    return field_service.request_otp_fieldlistid()

@app.route('/verify-otp-fieldlistid', methods=['POST'])
def route_verify_otp_fieldlistid():
    return field_service.verify_otp_fieldlistid()

@app.route("/getWKT/field/<field_list_id>", methods=["POST"])
def route_get_field_view(field_list_id):
    return field_service.get_field_view(field_list_id)

@app.route("/getWKT/mask/<fieldlistid>", methods=["GET"])
def route_get_mask_view(fieldlistid):
    return field_service.get_mask_view(fieldlistid)

@app.route('/decode_fieldlistid', methods=['POST'])
def route_decode_fieldlistid():
    return field_service.decode_fieldlistid()

@app.route('/qrcode_fieldlistid', methods=['GET'])
def route_generate_fieldlistid_qrcode():
    return field_service.generate_fieldlistid_qrcode()

@app.route('/lookup-user', methods=['POST'])
def route_lookup_user():
    return field_service.lookup_user()

@app.route('/field-list-ids')
def route_get_field_list_ids():
    return field_service.get_field_list_ids()

@app.route('/check_approved_user', methods=['POST'])
def route_heck_approved_user():
    return field_service.heck_approved_user()

@app.route("/get-geoids", methods=["POST"])
def route_get_geoids():
    return field_service.get_geoids()

@app.route("/get_fieldlists", methods=["POST"])
def route_get_fieldlists():
    return field_service.get_fieldlists()

@app.route('/get_user_data_acl', methods=['POST'])
def route_get_user_data_acl():
    return field_service.get_user_data_acl()

@app.route('/all-field-users')
def route_get_all_field_users():
    return field_service.get_all_field_users()

@app.route('/field-users/<field_list_id>', methods=['GET'])
def route_get_field_users(field_list_id):
    return field_service.get_field_users(field_list_id)

@app.route('/field-users/<fieldlistid>')
def route_get_users_for_field(fieldlistid):
    return field_service.get_users_for_field(fieldlistid)

@app.route('/link_fieldlistid', methods=['GET'])
def route_link_fieldlistid():
    return field_service.link_fieldlistid()

@app.route("/get_geoids_by_fieldlistid", methods=["GET"])
def route_get_geoids_by_fieldlistid():
    return field_service.get_geoids_by_fieldlistid()

@app.route("/create_facility", methods=["POST"])
def route_create_facility():
    return field_service.create_facility()

@app.route("/getWKT/facility/<facilityid>", methods=["GET"])
def route_get_facility_view(facilityid):
    return field_service.get_facility_view(facilityid)

@app.route("/request_access", methods=["POST"])
def route_request_access():
    return field_service.request_access()

@app.route("/pending_requests", methods=["GET"])
def route_pending_requests():
    return field_service.pending_requests()

@app.route("/approve_request", methods=["POST"])
def route_approve_request():
    return field_service.approve_request()

@app.route('/admin-acl')
def admin_acl_page():
    return render_template('admin_acl.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

@app.route('/login_page')
def login_page():
    return render_template('login.html')

@app.route('/create_fieldlistid')
def create_fieldlistid():
    return render_template('create_fieldlistid.html')

@app.route('/fildlist_page')
def fildlist_page():
    return render_template('fieldlists.html')

# ---------- fieldlistid map/qr code End -------------


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
