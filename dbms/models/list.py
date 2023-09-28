import random
import string

from dbms import db
from datetime import datetime


class Lists(db.Model):
    __tablename__ = 'lists'

    id = db.Column(db.Integer, primary_key=True, index=True)
    name = db.Column(db.String())
    uuid = db.Column(db.String(), unique=True, nullable=False)

    # Define the many-to-many relationship with GeoIds
    geo_ids = db.relationship('GeoIds', secondary='list_geo_ids', backref='lists')
    created_at = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return '<id {}>'.format(self.id)

    def __init__(self, *args, **kwargs):
        super(Lists, self).__init__(*args, **kwargs)
        uid = self.generate_uuid()
        while Lists.query.filter_by(uuid=uid).first() is not None:
            uid = self.generate_uuid()
        self.uuid = uid

    def generate_uuid(self):
        charset = string.hexdigits[:]
        formatted_uuid = '-'.join(''.join(random.choice(charset) for _ in range(8)) for _ in range(8))
        return formatted_uuid

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "uuid": self.uuid,
            "created_at": str(self.created_at),
            "geo_ids": [geoid.geo_id for geoid in self.geo_ids],
        }


