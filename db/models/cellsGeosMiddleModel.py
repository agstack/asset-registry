from app import db, app


class CellsGeosMiddle(db.Model):
    __tablename__ = 'cells_geo_ids'

    id = db.Column(db.Integer, primary_key=True)
    geo_id = db.Column(db.Integer, db.ForeignKey('geo_ids.id'))
    cell_id = db.Column(db.Integer, db.ForeignKey('s2_cell_tokens.id'))

    def __init__(self, geo_id, cell_id):
        self.geo_id = geo_id
        self.cell_id = cell_id

    def __repr__(self):
        return '<geo_id {}>'.format(self.geo_id)
