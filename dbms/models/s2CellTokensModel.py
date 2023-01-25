from dbms import db


class S2CellTokens(db.Model):
    __tablename__ = 's2_cell_tokens'

    id = db.Column(db.Integer, primary_key=True, index=True)
    cell_token = db.Column(db.String(), unique=True)

    def __init__(self, cell_token):
        self.cell_token = cell_token

    def __repr__(self):
        return '<id {}>'.format(self.id)
