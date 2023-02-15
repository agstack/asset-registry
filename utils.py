import json
import hashlib

import pyproj
import requests
import shapely
import jwt
from functools import wraps, partial
from flask import request, jsonify
from localStoragePy import localStoragePy
from shapely import ops
from shapely.wkt import loads
from shapely.geometry import mapping
import geojson

from dbms import app, db
from dbms.models.geoIdsModel import GeoIds
from dbms.models.s2CellTokensModel import S2CellTokens
from dbms.models.cellsGeosMiddleModel import CellsGeosMiddle

localStorage = localStoragePy('asset-registry', 'text')


class Utils:
    """
    Utils class for helper functions
    """

    # decorator for verifying  and fetching the JWT
    @staticmethod
    def fetch_token(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                # jwt is passed in the request header
                headers = request.headers
                bearer = headers.get('Authorization')  # Bearer JWT token here
                token = bearer.split()[1]  # JWT token
                # return 401 if token is not passed
                if not token:
                    return jsonify({'message': 'Token is missing !!'}), 401

                try:
                    # decoding the payload to fetch the stored details
                    jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")
                except:
                    localStorage.clear()
                    return jsonify({
                        'message': 'Token is invalid !!'
                    }), 401
                return f(token, *args, **kwargs)
            except:
                return jsonify({
                    'message': 'Authentication Error!'
                }), 401

        return decorated

    # decorator for checking if valid token provided
    @staticmethod
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            headers = request.headers
            bearer = headers.get('Authorization')  # Bearer JWT token here
            if bearer:
                token = bearer.split()[1]  # JWT token
            if token is None:
                token = localStorage.getItem('token')
            try:
                # decoding the payload to check for valid token
                decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")
                # check if user account is activated
                if not decoded_token['is_activated']:
                    return jsonify({
                        'message': 'User account not activated. Activate your account for the services.',
                    }), 401
            except Exception as e:
                localStorage.clear()
                return jsonify({
                    'message': 'Need to Login.',
                    'error': f'{e}'
                }), 401
            return f(*args, **kwargs)

        return decorated

    @staticmethod
    def records_s2_cell_tokens(s2_cell_tokens_dict: dict):
        """
        creates database records for the s2 cell tokens
        :param s2_cell_tokens_dict:
        :return:
        """
        # tokens_dict = {}
        tokens_dict_middle_table = {}
        for res_level, s2_cell_tokens in s2_cell_tokens_dict.items():
            records_list_s2_cell_tokens_middle_table = []
            for s2_cell_token in s2_cell_tokens:
                records_list_s2_cell_tokens_middle_table.append(S2CellTokens(cell_token=s2_cell_token))
            # tokens_dict is a dictionary with structure e.g. {res_level: s2_cell_token_records_for_the_db}
            tokens_dict_middle_table[res_level] = records_list_s2_cell_tokens_middle_table

        return tokens_dict_middle_table

    @staticmethod
    def generate_geo_id(s2_cell_tokens):
        """
        each list of `s2_index__L20_list` will always have a unique GEO_ID
        :param s2_cell_tokens:
        :return:
        """
        s2_tuple = tuple(s2_cell_tokens)
        m = hashlib.sha256()

        # encoding the s2 tokens list
        for s in s2_tuple:
            m.update(s.encode())
        geo_id = m.hexdigest()  # <-- geoid

        # order matters
        return geo_id

    @staticmethod
    def lookup_geo_ids(geo_id_to_lookup):
        """
        check if the geo id (field boundary) is already registered
        Returns the fetched Field WKT
        :param geo_id_to_lookup:
        :return:
        """
        exists = None
        record = GeoIds.query.filter(GeoIds.geo_id == geo_id_to_lookup).first()
        if record:
            exists = json.loads(record.geo_data)['wkt']
        return exists

    @staticmethod
    def register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_middle_table_dict, field_wkt):
        """
        registering the geo id (field boundary) in the database
        :param geo_id:
        :param indices:
        :param records_list_s2_cell_tokens_middle_table_dict:
        :param field_wkt:
        :return:
        """
        geo_data = {'wkt': field_wkt}
        authority_token = None
        domain = Utils.get_domain_from_jwt()
        if domain:
            authority_token = Utils.get_authority_token_for_domain(domain)
        geo_id_record = GeoIds(geo_id, geo_data, authority_token)
        # creating the json encoded geo_data for different resolution levels
        for res_level, s2_cell_tokens_records in records_list_s2_cell_tokens_middle_table_dict.items():
            geo_data[res_level] = indices[res_level]
            # linking the s2 cell token records with the geo id for the middle table
            existing_records = S2CellTokens.query.filter(
                S2CellTokens.cell_token.in_(
                    [s2_cell_tokens_record.cell_token for s2_cell_tokens_record in s2_cell_tokens_records]))
            existing_cell_tokens = [existing_record.cell_token for existing_record in list(existing_records)]
            ls_records_to_create = [s2_cell_tokens_record for s2_cell_tokens_record in s2_cell_tokens_records if
                                    s2_cell_tokens_record.cell_token not in existing_cell_tokens]
            geo_id_record.s2_cell_tokens = geo_id_record.s2_cell_tokens + ls_records_to_create + list(existing_records)
        geo_data = json.dumps(geo_data)
        geo_id_record.geo_data = geo_data

        # populating the cell tokens, geo id and the middle table in the database
        # bulk insertions for tables
        # return_defaults as True sets the Id for the record to be inserted
        db.session.bulk_save_objects([geo_id_record], return_defaults=True)
        db.session.bulk_save_objects(geo_id_record.s2_cell_tokens, return_defaults=True)
        ls_middle_table_records = [CellsGeosMiddle(geo_id=geo_id_record.id, cell_id=s2_cell_token_record.id) for
                                   s2_cell_token_record in geo_id_record.s2_cell_tokens]
        db.session.bulk_save_objects(ls_middle_table_records)
        db.session.commit()
        return geo_data

    @staticmethod
    def fetch_geo_ids_for_cell_tokens(s2_cell_tokens, domain):
        """
        fetch the geo ids which at least have one token from the tokens list given
        Optional domain filter
        :param s2_cell_tokens:
        :param domain:
        :return:
        """
        # fetching the distinct geo ids for the cell tokens
        geo_ids = []
        if domain:
            authority_token = Utils.get_authority_token_for_domain(domain)
            if authority_token:
                geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(
                    S2CellTokens.cell_token.in_(set(s2_cell_tokens)), GeoIds.authority_token == authority_token)
        else:
            geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(
                S2CellTokens.cell_token.in_(set(s2_cell_tokens)))
        geo_ids = [r.geo_id for r in geo_ids]
        return geo_ids

    @staticmethod
    def check_percentage_match(matched_geo_ids, s2_index__l13_list, resolution_level, threshold):
        """
        Return the Geo Ids which overlap for a certain threshold
        :param matched_geo_ids:
        :param s2_index__l13_list:
        :param resolution_level:
        :param threshold:
        :return:
        """
        percentage_matched_geo_ids = []
        for matched_geo_id in matched_geo_ids:
            # fetch s2 cell tokens against a geo id
            geo_id_cell_tokens = json.loads(GeoIds.query.filter(GeoIds.geo_id == matched_geo_id).first().geo_data)[
                str(resolution_level)]
            percentage_match = len(set(s2_index__l13_list) & set(geo_id_cell_tokens)) / float(
                len(set(s2_index__l13_list) | set(geo_id_cell_tokens))) * 100
            if percentage_match > threshold:
                percentage_matched_geo_ids.append(matched_geo_id)
        return percentage_matched_geo_ids

    @staticmethod
    def is_valid_polygon(field_wkt):
        """
        Check if a valid polygon
        :param field_wkt:
        :return:
        """
        try:
            poly = shapely.wkt.loads(field_wkt)
            if poly.geom_type == 'Polygon':
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False

    @staticmethod
    def get_percentage_overlap_two_fields(geo_id_field_1, geo_id_field_2):
        """
        Determine what is the % overlap of the 2 fields
        For Resolution Level 20
        Getting overlap of smaller field from the larger one
        :param geo_id_field_1:
        :param geo_id_field_2:
        :return:
        """
        try:
            field_1 = set(json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id_field_1).first().geo_data)[
                              str('20')])
            field_2 = set(json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id_field_2).first().geo_data)[
                              str('20')])
            overlap = field_1 & field_2
            percentage_overlap = (len(overlap) / len(field_1)) * 100 if len(field_1) > len(field_2) else (
                                                                                                                 len(overlap) / len(
                                                                                                             field_2)) * 100
        except AttributeError:
            raise AttributeError('Please provide valid Geo Ids.')
        return percentage_overlap

    @staticmethod
    def fetch_fields_for_cell_tokens(s2_cell_tokens_13, s2_cell_tokens_20, s2_index=None):
        """
        Checks if token exists in L13 and L20
        Two way search
        Fetch the fields
        :param s2_cell_tokens_20:
        :param s2_cell_tokens_13:
        :param s2_index:
        :return:
        """
        fields_to_return = []
        if s2_index:
            s2_index_to_fetch = [int(i) for i in s2_index.split(',')]
            s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)
        for s2_cell_token_13 in s2_cell_tokens_13:
            geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(
                S2CellTokens.cell_token == s2_cell_token_13)
            geo_ids = [r.geo_id for r in geo_ids]
        for geo_id in geo_ids:
            geo_data = json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id).first().geo_data)
            geo_data_to_return = None
            if s2_index and s2_indexes_to_remove != -1:
                geo_data_to_return = Utils.get_specific_s2_index_geo_data(json.dumps(geo_data), s2_indexes_to_remove)
            for s2_cell_token_20 in s2_cell_tokens_20:
                if s2_cell_token_20 in geo_data['20']:
                    fields_to_return.append({geo_id: geo_data_to_return})
                    break
        return fields_to_return

    @staticmethod
    def fetch_fields_for_a_point_two_way(s2_cell_token_13, s2_cell_token_20, domain, s2_index=None):
        """
        Checks if token exists in L13, then further checks for L20
        Returns the fields if token exists at both the levels
        Optional domain filter
        :param s2_cell_token_13:
        :param s2_cell_token_20:
        :param domain:
        :param s2_index:
        :return:
        """
        geo_ids = []
        if s2_index:
            s2_index_to_fetch = [int(i) for i in s2_index.split(',')]
            s2_indexes_to_remove = Utils.get_s2_indexes_to_remove(s2_index_to_fetch)
        if domain:
            authority_token = Utils.get_authority_token_for_domain(domain)
            if authority_token:
                geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(
                    S2CellTokens.cell_token == s2_cell_token_13, GeoIds.authority_token == authority_token)
        else:
            geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(
                S2CellTokens.cell_token == s2_cell_token_13)
        geo_ids = [r.geo_id for r in geo_ids]
        fields_to_return = []
        for geo_id in geo_ids:
            geo_data_to_return = None
            geo_data = json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id).first().geo_data)
            if s2_index and s2_indexes_to_remove != -1:
                geo_data_to_return = Utils.get_specific_s2_index_geo_data(json.dumps(geo_data), s2_indexes_to_remove)
            if s2_cell_token_13 in geo_data['13'] and s2_cell_token_20 in geo_data['20']:
                fields_to_return.append({geo_id: geo_data_to_return})
        return fields_to_return

    @staticmethod
    def get_domain_from_jwt():
        """
        Get domain of the logged in user
        :return:
        """
        token = localStorage.getItem('token')
        if not token:
            return None
        domain = jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")['domain']
        return domain

    @staticmethod
    def get_authority_token_for_domain(domain):
        """
        Fetch the authority token against a domain from User Registry
        :param domain:
        :return:
        """
        res = requests.get(app.config['USER_REGISTRY_BASE_URL'] + f'/authority-token/?domain={domain}', timeout=2)
        if res and res.json() and res.json().keys() and 'Authority Token' in res.json().keys():
            return res.json()['Authority Token']
        return None

    @staticmethod
    def get_s2_indexes_to_remove(s2_indexes):
        """
        Fetches the S2 indexes from the given list, which are not required in the JSON response
        :param s2_indexes:
        :return:
        """
        valid_s2_indexes_set = set([8, 13, 15, 18, 19, 20])
        s2_indexes_set = set(s2_indexes)
        if valid_s2_indexes_set & s2_indexes_set:
            return list(valid_s2_indexes_set - s2_indexes_set)
        else:
            return -1

    @staticmethod
    def get_specific_s2_index_geo_data(geo_data, s2_indexes_to_remove):
        """
        Get only specific S2 indexes data in geo_data (json data)
        :param geo_data:
        :param s2_indexes_to_remove:
        :return:
        """
        geo_data = json.loads(geo_data)
        for key in s2_indexes_to_remove:
            del geo_data[str(key)]
        return geo_data

    @staticmethod
    def get_are_in_acres(wkt):
        """
        Fetch the area in acres for the given field (wkt)
        :param wkt:
        :return:
        """
        geom = loads(wkt)
        geom_area = ops.transform(
            partial(
                pyproj.transform,
                pyproj.Proj(init='EPSG:4326'),
                pyproj.Proj(
                    proj='aea',
                    lat_1=geom.bounds[1],
                    lat_2=geom.bounds[3])),
            geom)

        # Return the area in km^2
        area_in_sq_km = geom_area.area / 1000000
        area_in_acres = area_in_sq_km * 247.105

        return area_in_acres

    @staticmethod
    def get_geo_json(field_wkt):
        """
        Fetch the Geo JSON for the given field WKT
        :param field_wkt:
        :return:
        """
        geojson_dict = {"type": "Feature"}
        geojson_string = geojson.dumps(mapping(loads(field_wkt)))
        geojson_dict["geometry"] = json.loads(geojson_string)
        return geojson_dict
