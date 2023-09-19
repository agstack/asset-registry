import datetime
from flask import jsonify
from sqlalchemy.exc import IntegrityError

from app import db
from flask_restful import reqparse
from flask import Blueprint
from flask_restful import Api, Resource

from dbms.models.geoIdsModel import GeoIds
from dbms.models.list import Lists
from utils import Utils

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
            parser.add_argument("geoids", type=list, default=[], location='json')  # List of geoid IDs

            args = parser.parse_args()

            # Create a new Product instance
            new_list = Lists()


            # Assign applications and product_offers based on their IDs

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

    # @Utils.token_required
    # def put(self, product_id):
    #     try:
    #         product = Product.query.get(product_id)
    #         if not product:
    #             return {"message": "Product not found"}, 404
    #
    #         parser = reqparse.RequestParser()
    #         parser.add_argument("name", type=str)
    #         parser.add_argument("description", type=str)
    #         parser.add_argument("premium", type=bool)
    #         parser.add_argument("applications", type=list, default=[], location='json')  # List of application IDs
    #         parser.add_argument("product_offers", type=list, default=[], location='json')  # List of product offer IDs
    #
    #         args = parser.parse_args()
    #
    #         try:
    #             if args["name"]:
    #                 product.name = args["name"]
    #             if args["description"]:
    #                 product.description = args["description"]
    #             if args["premium"] is not None:
    #                 product.premium = args["premium"]
    #
    #             if args["applications"]:
    #                 product.applications = []  # Clear existing applications
    #                 for app_id in args["applications"]:
    #                     app = Application.query.get(app_id)
    #                     if app:
    #                         product.applications.append(app)
    #                     else:
    #                         return {"message": f"This {app_id} application doesn't exist"}, 404
    #
    #                 # Check if product_offers should be updated
    #             if args["product_offers"]:
    #                 product.product_offers = []  # Clear existing product offers
    #                 for offer_id in args["product_offers"]:
    #                     offer = ProductOffer.query.get(offer_id)
    #                     if offer:
    #                         product.product_offers.append(offer)
    #                     else:
    #                         return {"message": f"This {offer_id} offer doesn't exist"}, 404
    #
    #             product.updated_at = datetime.datetime.now()
    #             db.session.commit()
    #         except IntegrityError as e:
    #             return {"message": f"A product with name {args['name']} already exists"}, 400
    #
    #         return {"message": "Product updated successfully", "product": product.as_dict()}, 200
    #     except Exception as e:
    #         return {"message": str(e)}, 400
    #
    # @Utils.token_required
    # def delete(self, product_id):
    #     product = Product.query.get(product_id)
    #     if not product:
    #         return {"message": "Product not found"}, 404
    #
    #     db.session.delete(product)
    #     db.session.commit()
    #
    #     return {"message": "Product deleted successfully"}


api.add_resource(ListResource, "/geoid-lists", "/geoid-lists/<int:list_id>")
