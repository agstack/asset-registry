from dbms import db
from datetime import datetime


class Lists(db.Model):
    __tablename__ = 'lists'

    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String())

    # Define the many-to-many relationship with GeoIds
    geo_ids = db.relationship('GeoIds', secondary='list_geo_ids', backref='lists')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return '<id {}>'.format(self.id)

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": str(self.created_at),
            "updated_at": str(self.updated_at),
            "geo_ids": [geoid.geo_id for geoid in self.geo_ids],
        }


