import json
import requests
from flask import jsonify, request, make_response
from flask_migrate import Migrate
from dbms import app, db
from s2_service import S2Service
from utils import Utils
from dotenv import load_dotenv
from shapely.geometry import Point
from shapely.wkt import loads as load_wkt
from flask_wtf.csrf import generate_csrf

load_dotenv()

from dbms.models import geoIdsModel, s2CellTokensModel, cellsGeosMiddleModel

migrate = Migrate(app, db)


@app.route('/', methods=["GET"])
@Utils.fetch_token
def index(token, refresh_token):
    """
    Endpoint to receive tokens from user-registry and return a response
    """
    try:
        to_return = {'access_token': token, 'refresh_token': refresh_token}
        return jsonify(to_return)
    except Exception as e:
        return jsonify({
            'message': 'Asset Registry Error',
            'error': f'{e}'
        }), 401


@app.route('/logout', methods=['GET'])
@Utils.token_required
def logout():
    try:
        refresh_token = Utils.get_bearer_token()
        if not refresh_token:
            return jsonify({
                'message': 'Asset Registry Logout Error',
                'error': 'No token.'
            }), 401
        resp_fe = make_response(jsonify({"message": "Successfully logged out"}), 200)
        # unset session cookies for postman response
        resp_fe.set_cookie('access_token_cookie', '', expires=0)
        resp_fe.set_cookie('refresh_token_cookie', '', expires=0)
        return resp_fe
    except Exception as e:
        return jsonify({
            'message': 'Asset Registry Logout Error',
            'error': f'{e}'
        }), 401


@app.route('/login', methods=['POST'])
def login():
    if request.is_json:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        if email is None or password is None:
            return jsonify({'message': 'Missing arguments'}), 400
        data['asset_registry'] = True
        try:
            res = requests.post(app.config['USER_REGISTRY_BASE_URL'], json=data)
            json_res = json.loads(res.content.decode())

        except Exception as e:
            return jsonify({
                'message': 'User Registry Error',
                'error': f'{e}'
            }), 401
        if res.status_code == 200:
            try:
                response_fe = make_response(jsonify(json_res), 200)
                response_fe.set_cookie('refresh_token_cookie', json_res.get('refresh_token'))
                response_fe.set_cookie('access_token_cookie', json_res.get('access_token'))
                return response_fe
            except TypeError:
                response_fe = make_response(jsonify(json_res), 401)
                return response_fe
        else:
            response_fe = make_response(jsonify(json_res), 401)
            return response_fe
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
        # set lat lng from geoJson first coordinate.
        lat = field_boundary_geo_json['geometry']['coordinates'][0][0][1]
        lng = field_boundary_geo_json['geometry']['coordinates'][0][0][0]
        p = Point([lng, lat])
        country = Utils.get_country_from_point(p)
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
                                                     field_wkt, country)
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
                                                         field_wkt, country)
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
        # noinspection PyPackageRequirements
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
        }), 401


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
        }), 401


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
        }), 401


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


if __name__ == '__main__':
    app.run(host='0.0.0.0')
