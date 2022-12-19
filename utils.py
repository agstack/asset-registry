import json
import hashlib

from app import db
from db.models.geoIdsModel import GeoIds


class Utils:
    """
    Utils class for helper functions
    """

    @staticmethod
    def generate_geo_id(s2_tokens):
        """
        each list of `s2_index__L20_list` will always have a unique GEO_ID
        """
        s2_tuple = tuple(s2_tokens)
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
    def register_field_boundary(geo_id, s2_cell_tokens, resolution_level):
        """
        registering the geo id (field boundary) in the database
        """
        geo_data = json.dumps({'s2_L' + str(resolution_level): s2_cell_tokens})
        geo_id_record = GeoIds(geo_id, geo_data)
        db.session.add(geo_id_record)
        db.session.commit()
        return
