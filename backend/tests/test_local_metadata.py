from sqlalchemy import select

from app.db.models import Theme
from app.services.local_metadata import update_missing_local_metadata
from tests.factories import add_catalog_set, add_owned_set, add_theme


def test_update_missing_local_metadata_sets_age_and_parent_theme(
    db_session, tmp_path
) -> None:
    age_csv = tmp_path / "age.csv"
    age_csv.write_text("set_number,age\n60181,5+\n6024,7+\n", encoding="utf-8")
    sets_csv = tmp_path / "sets.csv"
    sets_csv.write_text(
        "set_num,name,year,theme_id,num_parts,img_url\n"
        "60181-1,Forest Tractor,2018,57,174,\n"
        "6024-1,Police Car,1980,67,24,\n",
        encoding="utf-8",
    )
    themes_csv = tmp_path / "themes.csv"
    themes_csv.write_text(
        "id,name,parent_id\n"
        "52,City,\n"
        "57,Farm,52\n"
        "50,Town,\n"
        "67,Classic Town,50\n",
        encoding="utf-8",
    )
    missing = add_catalog_set(db_session, set_number=60181)
    missing_owned = add_owned_set(db_session, missing)
    existing_theme = add_theme(db_session, external_id=99, name="Existing")
    existing = add_catalog_set(db_session, set_number=6024, theme=existing_theme)
    existing_owned = add_owned_set(db_session, existing)
    existing_owned.age = 9
    db_session.commit()

    result = update_missing_local_metadata(
        db_session,
        age_csv_path=str(age_csv),
        sets_csv_path=str(sets_csv),
        themes_csv_path=str(themes_csv),
    )
    db_session.commit()

    assert result.owned_set_ages_updated == 1
    assert result.catalog_themes_updated == 1
    assert result.age_values_available == 2
    assert result.theme_values_available == 2
    assert missing_owned.age == 5
    assert existing_owned.age == 9
    city = db_session.scalar(select(Theme).where(Theme.external_id == 52))
    assert city is not None
    assert city.name == "City"
    assert missing.theme_id == city.id
    assert existing.theme_id == existing_theme.id
