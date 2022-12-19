from app import db, app


class GeoIds(db.Model):
    __tablename__ = 'geo_ids'

    id = db.Column(db.Integer, primary_key=True)
    geo_id = db.Column(db.String(), unique=True)
    geo_data = db.Column(db.JSON)
    cell_geo_ids = db.relationship('CellsGeosMiddle', backref='geo_ids')

    def __init__(self, geo_id, geo_data):
        self.geo_id = geo_id
        self.geo_data = geo_data

    def __repr__(self):
        return '<id {}>'.format(self.id)
