from dbms.models.list import Lists


def list_exists(listt):
    same_list = False

    for geoid in listt:
        existing_list = Lists.query.filter(Lists.geo_ids.any(id=geoid)).all()
        if existing_list:
            for existing_listt in existing_list:
                if set([geoid.id for geoid in existing_listt.geo_ids]) == set(listt):
                    same_list = True
                    break

    return same_list