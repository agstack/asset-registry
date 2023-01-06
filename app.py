import json
import fiona
import geopandas as gpd
from flask import jsonify, request, make_response
from flask_migrate import Migrate
from db import app, db
from s2_service import S2Service
from utils import Utils

from dotenv import load_dotenv

load_dotenv()

from db.models import geoIdsModel, s2CellTokensModel, cellsGeosMiddleModel

migrate = Migrate(app, db)


@app.route('/kml-to-wkt', methods=['POST'])
def convert_kml_to_wkt():
    kml_file = request.files.get('kml')

    fiona.supported_drivers['KML'] = 'rw'
    f = fiona.BytesCollection(bytes(kml_file.content))
    df = gpd.GeoDataFrame()

    gdf = gpd.read_file(kml_file, driver='KML')
    poly = gdf.geometry.iloc[0]  # shapely polygon
    wkt = poly.wkt


@app.route('/register-field-boundary', methods=['POST'])
def register_field_boundary():
    """
    Registering a field boundary against a Geo Id
    """
    data = json.loads(request.data.decode('utf-8'))
    field_wkt = data.get('wkt')

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
    # lookup the database to see if geo id already exists
    geo_id_exists = Utils.lookup_geo_ids(geo_id)
    # if geo id not registered, register it in the database
    if not geo_id_exists:
        geo_data = Utils.register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_middle_table_dict)
        return jsonify({
            "Message": "Field Boundary registered successfully.",
            "GEO ID": geo_id,
            "S2 Cell Tokens": geo_data
        })
    else:
        return make_response(jsonify({
            "Message": "Field Boundary already registered."
        }), 200)


@app.route('/fetch-overlapping-fields', methods=['GET'])
def fetch_overlapping_fields():
    """
    Fetch the overlapping fields for a certain threshold
    Overlap is being checked for L13 Resolution Level
    Returning the fields Geo Ids
    """
    data = json.loads(request.data.decode('utf-8'))
    field_wkt = data.get('wkt')
    resolution_level = data.get('resolution_level')
    threshold = data.get('threshold')

    # get the L13 indices
    # s2_index__L13_list is a list of tokens(hex encoded version of the cell id)
    s2_index__l13_list = S2Service.wkt_to_cell_tokens(field_wkt, resolution_level)

    # fetch geo ids for tokens and checking for the percentage match
    matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index__l13_list)
    percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index__l13_list, resolution_level,
                                                              threshold)

    return make_response(jsonify({
        "Message": "The field Geo Ids with percentage match of at least 90%.",
        "GEO Ids": percentage_matched_geo_ids
    }), 200)


@app.route('/fetch-field/<geo_id>', methods=['GET'])
def fetch_field(geo_id):
    """
    Fetch a Field (S2 cell tokens) for the provided Geo Id
    :param geo_id:
    :return:
    """
    field = geoIdsModel.GeoIds.query \
        .filter_by(geo_id=geo_id) \
        .first()
    if not field:
        return make_response(jsonify({
            "Message": "Field not found, invalid Geo Id."
        }), 404)
    return make_response(jsonify({
        "Message": "Field fetched successfully.",
        "GEO Ids": field.geo_data
    }), 200)


@app.route('/get-percentage-overlap-two-fields', methods=['POST'])
def get_percentage_overlap_two_fields():
    """
    Passed in 2 GeoIDs, determine what is the % overlap of the 2 fields
    :return:
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        geo_id_field_1 = data.get('geo_id_field_1')
        geo_id_field_2 = data.get('geo_id_field_2')
        if not geo_id_field_1 or not geo_id_field_2:
            return make_response(jsonify({
                "Message": "Two Geo Ids are required."
            }), 400)

        percentage_overlap = Utils.get_percentage_overlap_two_fields(geo_id_field_1, geo_id_field_2)
    except AttributeError as error:
        return make_response(jsonify({
            "Message": str(error)
        }), 404)

    return make_response(jsonify({
        "Percentage Overlap": str(percentage_overlap) + ' %'
    }), 200)


@app.route('/fetch-fields-for-a-point', methods=['POST'])
def fetch_fields_for_a_point():
    """
    Fetch all the fields containing the point
    Latitude and Longitude provided
    Check for L13 and L20
    Two stage search
    :return:
    """
    try:
        data = json.loads(request.data.decode('utf-8'))
        lat = data.get('latitude')
        long = data.get('longitude')
        if not lat or not long:
            return make_response(jsonify({
                "Message": "Latitude and Longitude are required."
            }), 400)
        s2_cell_token_13, s2_cell_token_20 = S2Service.get_cell_token_for_lat_long(lat, long)
        fetched_fields = Utils.fetch_fields_for_a_point_two_way(s2_cell_token_13, s2_cell_token_20)
        return make_response(jsonify({
            "Fetched fields": fetched_fields
        }), 200)
    except AttributeError as error:
        return make_response(jsonify({
            "Message": str(error)
        }), 404)


@app.route('/fetch-bounding-box-fields', methods=['POST'])
def fetch_bounding_box_fields():
    """
    Fetch the fields intersecting the Bounding Box
    4 vertices are provided
    :return:
    """
    data = json.loads(request.data.decode('utf-8'))
    latitudes = list(map(float, data.get('latitudes').split(' ')))
    longitudes = list(map(float, data.get('longitudes').split(' ')))
    if not latitudes or not longitudes:
        return make_response(jsonify({
            "Message": "Latitudes and Longitudes are required."
        }), 400)
    s2_cell_tokens = S2Service.get_cell_tokens_for_bounding_box(latitudes, longitudes)
    fields = Utils.fetch_fields_for_cell_tokens(s2_cell_tokens)
    return make_response(jsonify({
        "Message": fields
    }), 200)
