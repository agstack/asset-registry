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
    data = json.loads(request.data.decode('utf-8'))
    field_wkt = data.get('wkt')
    resolution_level = data.get('resolution_level')

    # get the L13 indices
    # s2_index__L13_list is a list of tokens(hex encoded version of the cell id)
    s2_index__l13_list = S2Service.wkt_to_cell_ids(field_wkt, resolution_level)

    # generate the geo_id only for `s2_index__l13_list`
    geo_id = Utils.generate_geo_id(s2_index__l13_list)

    # lookup the database to see if geo id already exists
    geo_id_exists = Utils.lookup_geo_ids(geo_id)

    # if geo id not registered, register it in the database
    if not geo_id_exists:
        Utils.register_field_boundary(geo_id, s2_index__l13_list, resolution_level)
        return jsonify({
            "Message": "Field Boundary registered successfully.",
            "GEO ID": geo_id,
            "S2 Cell Tokens": s2_index__l13_list
        })
    else:
        return jsonify({
            "Message": "Field Boundary already registered."
        })
