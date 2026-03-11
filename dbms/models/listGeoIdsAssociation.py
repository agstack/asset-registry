from dbms import db


class ListGeoIdsAssociation(db.Model):
    __tablename__ = 'list_geo_ids'

    id = db.Column(db.Integer, primary_key=True, index=True)
    list_id = db.Column(db.Integer, db.ForeignKey('lists.id'))
    geo_id = db.Column(db.Integer, db.ForeignKey('geo_ids.id'))

    def __init__(self, list_id, geo_id):
        self.list_id = list_id
        self.geo_id = geo_id

    def __repr__(self):
        return '<list_id {}>'.format(self.list_id)
