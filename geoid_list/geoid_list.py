import datetime

from flask import jsonify

from app import db
from flask_restful import reqparse
from flask import Blueprint
from flask_restful import Api, Resource

from dbms.models.geoIdsModel import GeoIds
from dbms.models.list import Lists
from geoid_list.utils import list_exists

list_bp = Blueprint("list_api", __name__)
api = Api(list_bp)


class ListResource(Resource):
    def get(self, list_id=None):
        if list_id is None:
            lists = Lists.query.all()
            result = []
            for listt in lists:
                result.append({
                    "id": listt.id,
                    "name": listt.name,
                    "geo_ids": [geoid.geo_id for geoid in listt.geo_ids]
                })
            return jsonify(result)
        else:
            listt = Lists.query.get(list_id)
            if listt:
                result = {
                    "id": listt.id,
                    "name": listt.name,
                    "geo_ids": [geoid.geo_id for geoid in listt.geo_ids]
                }
                return jsonify(result)
            else:
                return {"message": "List not found"}, 404

    def post(self):
        try:
            parser = reqparse.RequestParser()
            parser.add_argument("geoids", type=list, default=[], location='json', required=True)  # List of geoid IDs

            args = parser.parse_args()

            args["geoids"] = list(set(args["geoids"]))  # Remove duplicates
            new_list = Lists()
            same_list = list_exists(args["geoids"])
            if same_list:
                return {"message": f"A list with same geoids already exists"}, 400



            for geoid in args["geoids"]:
                rec = GeoIds.query.get(geoid)
                if rec:
                    new_list.geo_ids.append(rec)
                else:
                    return {"message": f"This {geoid} geoid doesn't exist"}, 404

            db.session.add(new_list)
            db.session.commit()

            return {"message": "List created successfully", "list": new_list.as_dict()}, 201
        except Exception as e:
            return {"message": str(e)}, 400

    def put(self, list_id):
        try:
            listt = Lists.query.get(list_id)
            if not listt:
                return {"message": "List not found"}, 404

            parser = reqparse.RequestParser()
            parser.add_argument("name", type=str)
            parser.add_argument("geoids", type=list, default=[], location='json')  # List of geoid IDs

            args = parser.parse_args()

            if args["name"]:
                listt.name = args["name"]
            if args["geoids"]:
                args["geoids"] = list(set(args["geoids"]))  # Remove duplicates
                same_list = list_exists(args["geoids"])
                if same_list:
                    return {"message": f"A list with same geoids already exists"}, 400
                listt.geo_ids = []  # Clear existing applications
                for geoid in args["geoids"]:
                    geo = GeoIds.query.get(geoid)
                    if geo:
                        listt.geo_ids.append(geo)
                    else:
                        return {"message": f"This {geoid} geoid doesn't exist"}, 404

            listt.updated_at = datetime.datetime.now()
            db.session.commit()

            return {"message": "List updated successfully", "list": listt.as_dict()}, 200
        except Exception as e:
            return {"message": str(e)}, 400

    def delete(self, list_id):
        listt = Lists.query.get(list_id)
        if not listt:
            return {"message": "List not found"}, 404

        db.session.delete(listt)
        db.session.commit()

        return {"message": "List deleted successfully"}


api.add_resource(ListResource, "/geoid-lists", "/geoid-lists/<int:list_id>")
