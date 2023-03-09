import json
# import fiona
import geopandas as gpd
import requests
from localStoragePy import localStoragePy
from flask import jsonify, request, make_response
from flask_migrate import Migrate
from dbms import app, db
from s2_service import S2Service
from utils import Utils

from dotenv import load_dotenv

load_dotenv()
localStorage = localStoragePy('asset-registry', 'text')

from dbms.models import geoIdsModel, s2CellTokensModel, cellsGeosMiddleModel

migrate = Migrate(app, db)


@app.route('/', methods=["GET"])
@Utils.fetch_token
def index(token):
    """
    Endpoint to receive tokens from user-registry and return a response
    """
    if request.is_json:
        if token is not None:
            return jsonify({"token": token})
        else:
            return jsonify({'message': 'No token found'})
    try:
        if token is not None:
            localStorage.setItem('token', token)
            status = 200
        else:
            status = 204
        to_return = {'status': status}
        return jsonify(to_return)
    except Exception as e:
        return jsonify({
            'message': 'Asset Registry Error',
            'error': f'{e}'
        }), 401


@app.route('/logout', methods=['GET'])
@Utils.token_required
def logout():
    localStorage.clear()
    return jsonify({
        "message": "Logged out successfully."
    })


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


@app.route('/register-field-boundary', methods=['POST'])
@Utils.token_required
def register_field_boundary():
    """
    Registering a field boundary against a Geo Id
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        field_wkt = data.get('wkt')
        threshold = data.get('threshold') or 95
        resolution_level = 20
        field_boundary_geo_json = Utils.get_geo_json(field_wkt)
        are_in_acres = Utils.get_are_in_acres(field_wkt)
        if are_in_acres > 1000:
            return make_response(jsonify({
                "message": f"Cannot register a field with Area greater than 1000 acres",
                "Field area (acres)": are_in_acres
            }), 200)

        s2_index = data.get('s2_index')
        if s2_index:
            s2_index_to_fetch = [int(i) for i in (data.get('s2_index')).split(',')]
            s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)

        # get the Different resolution level indices
        # list against a key (e.g. 13) is a list of tokens(hex encoded version of the cell id)
        indices = {8: S2Service.wkt_to_cell_tokens(field_wkt, 8),
                   13: S2Service.wkt_to_cell_tokens(field_wkt, 13),
                   15: S2Service.wkt_to_cell_tokens(field_wkt, 15),
                   18: S2Service.wkt_to_cell_tokens(field_wkt, 18),
                   19: S2Service.wkt_to_cell_tokens(field_wkt, 19),
                   20: S2Service.wkt_to_cell_tokens(field_wkt, 20),
                   }

        # fetching the new s2 cell tokens records for different Resolution Levels, to be added in the database
        records_list_s2_cell_tokens_middle_table_dict = Utils.records_s2_cell_tokens(indices)
        # generate the geo_id only for `s2_index__l13_list`
        geo_id = Utils.generate_geo_id(indices[13])
        geo_id_l20 = Utils.generate_geo_id(indices[20])
        # lookup the database to see if geo id already exists
        geo_id_exists_wkt = Utils.lookup_geo_ids(geo_id)
        # if geo id not registered, register it in the database
        if not geo_id_exists_wkt:
            geo_data_to_return = None
            geo_data = Utils.register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_middle_table_dict,
                                                     field_wkt)
            if s2_index and s2_indexes_to_remove != -1:
                geo_data_to_return = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
            return jsonify({
                "message": "Field Boundary registered successfully.",
                "Geo Id": geo_id,
                "S2 Cell Tokens": geo_data_to_return,
                "Geo JSON": field_boundary_geo_json
            })
        else:
            # check for the percentage match for the given threshold for L20
            # get the L20 indices
            # s2_index__L20_list is a list of tokens(hex encoded version of the cell id)
            s2_index_to_check = indices[20]
            # fetch geo ids for tokens and checking for the percentage match
            matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index_to_check, "")
            percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index_to_check,
                                                                      resolution_level,
                                                                      threshold)
            if len(percentage_matched_geo_ids) > 0:
                return jsonify({
                    'message': 'Threshold matched for already registered Field Boundary(ies)',
                    'matched geo ids': percentage_matched_geo_ids
                }), 400

            geo_id_exists_wkt_l20 = Utils.lookup_geo_ids(geo_id_l20)
            if not geo_id_exists_wkt_l20:
                geo_data_to_return = None
                geo_data = Utils.register_field_boundary(geo_id_l20, indices,
                                                         records_list_s2_cell_tokens_middle_table_dict,
                                                         field_wkt)
                if s2_index and s2_indexes_to_remove != -1:
                    geo_data_to_return = Utils.get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove)
                return jsonify({
                    "message": "Field Boundary registered successfully.",
                    "Geo Id": geo_id,
                    "S2 Cell Tokens": geo_data_to_return,
                    "Geo JSON": field_boundary_geo_json
                })
            else:
                return make_response(jsonify({
                    "message": f"Field Boundary already registered.",
                    "Geo Id": geo_id_l20,
                    "Geo JSON requested": field_boundary_geo_json,
                    "Geo JSON registered": Utils.get_geo_json(geo_id_exists_wkt_l20)
                }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Register Field Boundary Error',
            'error': f'{e}'
        }), 401


@app.route('/fetch-overlapping-fields', methods=['POST'])
@Utils.token_required
def fetch_overlapping_fields():
    """
    Fetch the overlapping fields for a certain threshold
    Overlap is being checked for L13 Resolution Level
    Optional domain parameter for filtering fields based on associated domain
    Returning the fields Geo Ids
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        field_wkt = data.get('wkt')
        resolution_level = data.get('resolution_level') or 13
        threshold = data.get('threshold') or 95
        s2_index = data.get('s2_index')
        domain = data.get('domain') or ""

        # get the L13 indices
        # s2_index__L13_list is a list of tokens(hex encoded version of the cell id)
        s2_index__l13_list = S2Service.wkt_to_cell_tokens(field_wkt, resolution_level)

        # fetch geo ids for tokens and checking for the percentage match
        matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index__l13_list, domain)
        percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index__l13_list, resolution_level,
                                                                  threshold)
        percentage_matched_fields = Utils.fetch_fields_for_geo_ids(percentage_matched_geo_ids, s2_index)

        return make_response(jsonify({
            "message": "The field Geo Ids with percentage match of the given threshold.",
            "Matched Fields": percentage_matched_fields
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Overlapping Fields Error',
            'error': f'{e}'
        }), 401


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
        }), 401


@app.route('/fetch-field-wkt/<geo_id>', methods=['GET'])
def fetch_field_wkt(geo_id):
    """
    Fetch a Field WKT for the provided Geo Id
    :param geo_id:
    :return:
    """
    try:
        field = geoIdsModel.GeoIds.query \
            .filter_by(geo_id=geo_id) \
            .first()
        if not field:
            return make_response(jsonify({
                "message": "Field not found, invalid Geo Id."
            }), 404)
        return make_response(jsonify({
            "message": "WKT fetched successfully.",
            "GEO Id": geo_id,
            "WKT": json.loads(field.geo_data)['wkt']
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Field WKT Error',
            'error': f'{e}'
        }), 401


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
        }), 401


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
        s2_index = data.get('s2_index')
        if not lat or not long:
            return make_response(jsonify({
                "message": "Latitude and Longitude are required."
            }), 400)
        s2_cell_token_13, s2_cell_token_20 = S2Service.get_cell_token_for_lat_long(lat, long)
        fetched_fields = Utils.fetch_fields_for_a_point_two_way(s2_cell_token_13, s2_cell_token_20, domain, s2_index)
        return make_response(jsonify({
            "Fetched fields": fetched_fields
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Fields for a Point Error',
            'error': f'{e}'
        }), 401


@app.route('/fetch-bounding-box-fields', methods=['POST'])
@Utils.token_required
def fetch_bounding_box_fields():
    """
    Fetch the fields intersecting the Bounding Box
    4 vertices are provided
    :return:
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        latitudes = list(map(float, data.get('latitudes').split(' ')))
        longitudes = list(map(float, data.get('longitudes').split(' ')))
        s2_index = data.get('s2_index')
        if not latitudes or not longitudes:
            return make_response(jsonify({
                "message": "Latitudes and Longitudes are required."
            }), 400)
        s2_cell_tokens_13 = S2Service.get_cell_tokens_for_bounding_box(latitudes, longitudes)
        s2_cell_tokens_20 = S2Service.get_cell_tokens_for_bounding_box(latitudes, longitudes, 20)
        fields = Utils.fetch_fields_for_cell_tokens(s2_cell_tokens_13, s2_cell_tokens_20, s2_index)
        return make_response(jsonify({
            "message": fields
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Bounding Box Fields Error',
            'error': f'{e}'
        }), 401


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
        "message": res.json()["message"]
    }), 200


@app.route('/fetch-field-count-date-range', methods=['GET'])
def fetch_field_count_date_range():
    """
    Fetch Registered Field By Date Count
    Query Param start_date end_date are provided
    :return:
    """
    try:
        args = request.args
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        print(start_date, end_date)
        if start_date is None or end_date is None:
            return make_response(jsonify({
                "message": "start_date and end_date is required.",
            }), 400)
        count = geoIdsModel.GeoIds.query \
            .filter(geoIdsModel.GeoIds.created_at.between(start_date, end_date)) \
            .count()
        return make_response(jsonify({
            "message": "fetched Count By Date successfully.",
            "count": count,
        }), 200)
    except Exception as e:
        return jsonify({
            'message': 'Fetch Field Count By Date Error',
            'error': f'{e}'
        }), 401


if __name__ == '__main__':
    app.run(host='0.0.0.0')
