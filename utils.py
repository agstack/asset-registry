import json
import hashlib

import shapely

from app import db
from db.models.geoIdsModel import GeoIds
from db.models.s2CellTokensModel import S2CellTokens
from db.models.cellsGeosMiddleModel import CellsGeosMiddle


class Utils:
    """
    Utils class for helper functions
    """

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
        :param geo_id_to_lookup:
        :return:
        """
        exists = db.session.query(GeoIds.id).filter_by(geo_id=geo_id_to_lookup).first() is not None
        return exists

    @staticmethod
    def register_field_boundary(geo_id, indices, records_list_s2_cell_tokens_middle_table_dict):
        """
        registering the geo id (field boundary) in the database
        :param geo_id:
        :param indices:
        :param records_list_s2_cell_tokens_middle_table_dict:
        :return:
        """
        geo_data = {}
        geo_id_record = GeoIds(geo_id, geo_data)
        # creating the json encoded geo_data for different resolution levels
        for res_level, s2_cell_tokens_records in records_list_s2_cell_tokens_middle_table_dict.items():
            geo_data[res_level] = indices[res_level]
            # linking the s2 cell token records with the geo id for the middle table
            for s2_cell_token_record in s2_cell_tokens_records:
                if not S2CellTokens.query.filter(S2CellTokens.cell_token == s2_cell_token_record.cell_token).first():
                    geo_id_record.s2_cell_tokens.append(s2_cell_token_record)
                else:
                    s2_cell_token_from_db = S2CellTokens.query.filter(S2CellTokens.cell_token == s2_cell_token_record.cell_token).first()
                    geo_id_record.s2_cell_tokens.append(s2_cell_token_from_db)

        geo_data = json.dumps(geo_data)
        geo_id_record.geo_data = geo_data

        # populating the cell tokens, geo id and the middle table in the database
        db.session.add(geo_id_record)
        db.session.commit()
        return geo_data

    @staticmethod
    def fetch_geo_ids_for_cell_tokens(s2_cell_tokens):
        """
        fetch the geo ids which at least have one token from the tokens list given
        :param s2_cell_tokens:
        :return:
        """
        # fetching the distinct geo ids for the cell tokens
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
        For Resolution Level 13
        Getting overlap of smaller field from the larger one
        :param geo_id_field_1:
        :param geo_id_field_2:
        :return:
        """
        try:
            field_1 = set(json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id_field_1).first().geo_data)[
                str('13')])
            field_2 = set(json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id_field_2).first().geo_data)[
                str('13')])
            overlap = field_1 & field_2
            percentage_overlap = (len(overlap) / len(field_1)) * 100 if len(field_1) > len(field_2) else (len(overlap) / len(field_2)) * 100
        except AttributeError:
            raise AttributeError('Please provide valid Geo Ids.')
        return percentage_overlap

    @staticmethod
    def fetch_fields_for_cell_tokens(s2_cell_tokens_13):
        """
        Checks if token exists in L13
        Fetch the fields
        :param s2_cell_tokens_13:
        :return:
        """
        fields_to_return = []
        for s2_cell_token_13 in s2_cell_tokens_13:
            geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(S2CellTokens.cell_token == s2_cell_token_13)
            geo_ids = [r.geo_id for r in geo_ids]
        for geo_id in geo_ids:
            geo_data = json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id).first().geo_data)
            if s2_cell_token_13 in geo_data['13']:
                fields_to_return.append({geo_id: geo_data})
        return fields_to_return

    @staticmethod
    def fetch_fields_for_a_point_two_way(s2_cell_token_13, s2_cell_token_20):
        """
        Checks if token exists in L13, then further checks for L20
        Returns the fields if token exists at both the levels
        :param s2_cell_token_13:
        :param s2_cell_token_20:
        :return:
        """
        geo_ids = db.session.query(GeoIds.geo_id).distinct().join(CellsGeosMiddle).join(S2CellTokens).filter(S2CellTokens.cell_token == s2_cell_token_13)
        geo_ids = [r.geo_id for r in geo_ids]
        fields_to_return = []
        for geo_id in geo_ids:
            geo_data = json.loads(GeoIds.query.filter(GeoIds.geo_id == geo_id).first().geo_data)
            if s2_cell_token_13 in geo_data['13'] and s2_cell_token_20 in geo_data['20']:
                fields_to_return.append({geo_id: geo_data})
        return fields_to_return
