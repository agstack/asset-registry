import json
import hashlib

from app import db
from db.models.geoIdsModel import GeoIds
from db.models.s2CellTokensModel import S2CellTokens


class Utils:
    """
    Utils class for helper functions
    """

    @staticmethod
    def records_s2_cell_tokens(s2_cell_tokens: list):
        """
        creates database records for the s2 cell tokens
        """
        all_saved_s2_cell_tokens = S2CellTokens.query.filter(S2CellTokens.cell_token.in_(set(s2_cell_tokens)))
        all_saved_s2_cell_tokens = [r.cell_token for r in all_saved_s2_cell_tokens]

        # checks for new S2 cell tokens to be added in the database and not repeating any
        to_add_s2_cell_tokens = list(set(s2_cell_tokens) - set(all_saved_s2_cell_tokens))
        records_list_s2_cell_tokens = []
        for to_add_s2_cell_token in to_add_s2_cell_tokens:
            records_list_s2_cell_tokens.append(S2CellTokens(cell_token=to_add_s2_cell_token))
        return records_list_s2_cell_tokens

    @staticmethod
    def generate_geo_id(s2_cell_tokens):
        """
        each list of `s2_index__L20_list` will always have a unique GEO_ID
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
        """
        exists = db.session.query(GeoIds.id).filter_by(geo_id=geo_id_to_lookup).first() is not None
        return exists

    @staticmethod
    def register_field_boundary(geo_id, s2_cell_tokens, records_list_s2_cell_tokens, resolution_level):
        """
        registering the geo id (field boundary) in the database
        """
        geo_data = json.dumps({'s2_L' + str(resolution_level): s2_cell_tokens})
        geo_id_record = GeoIds(geo_id, geo_data)
        # linking the s2 cell tokens and with the geo id for the middle table
        for s2_cell_token_record in records_list_s2_cell_tokens:
            geo_id_record.s2_cell_tokens.append(s2_cell_token_record)

        # populating the cell tokens, geo id and the middle table in the database
        db.session.add(geo_id_record)
        db.session.add_all(records_list_s2_cell_tokens)
        db.session.commit()
        return
