import json
import fiona
import geopandas as gpd
from flask import jsonify, request
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
    resolution_level = data.get('resolution_level')

    # get the Different resolution level indices
    # list against a key (e.g. 13) is a list of tokens(hex encoded version of the cell id)
    indices = {8: S2Service.wkt_to_cell_ids(field_wkt, 8),
               13: S2Service.wkt_to_cell_ids(field_wkt, 13),
               15: S2Service.wkt_to_cell_ids(field_wkt, 15),
               18: S2Service.wkt_to_cell_ids(field_wkt, 18),
               19: S2Service.wkt_to_cell_ids(field_wkt, 19),
               20: S2Service.wkt_to_cell_ids(field_wkt, 20),
               }

    # fetching the new s2 cell tokens records for different Resolution Levels, to be added in the database
    records_list_s2_cell_tokens_dict = Utils.records_s2_cell_tokens(indices)

    # generate the geo_id only for `s2_index__l13_list`
    geo_id = Utils.generate_geo_id(indices[13])

    # lookup the database to see if geo id already exists
    geo_id_exists = Utils.lookup_geo_ids(geo_id)

    # if geo id not registered, register it in the database
    if not geo_id_exists:
        geo_data = Utils.register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_dict)
        return jsonify({
            "Message": "Field Boundary registered successfully.",
            "GEO ID": geo_id,
            "S2 Cell Tokens": geo_data
        })
    else:
        return jsonify({
            "Message": "Field Boundary already registered."
        })


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

    # get the L13 indices
    # s2_index__L13_list is a list of tokens(hex encoded version of the cell id)
    s2_index__l13_list = S2Service.wkt_to_cell_ids(field_wkt, resolution_level)

    # fetch geo ids for tokens and checking for the percentage match
    matched_geo_ids = Utils.fetch_geo_ids_for_cell_tokens(s2_index__l13_list)
    percentage_matched_geo_ids = Utils.check_percentage_match(matched_geo_ids, s2_index__l13_list, resolution_level)

    return jsonify({
        "Message": "The field Geo Ids with percentage match of at least 90%.",
        "GEO Ids": percentage_matched_geo_ids
    })
