from app.common.pii import mask_contact_info, mask_cv_pii


def test_mask_contact_info_masks_email_address() -> None:
    text = "Contact: jane.doe@example.com for details"

    masked = mask_contact_info(text)

    assert "jane.doe@example.com" not in masked
    assert "[EMAIL]" in masked


def test_mask_contact_info_masks_tunisian_phone_with_country_code() -> None:
    text = "jane.doe@example.com – +216 23 147 963"

    masked = mask_contact_info(text)

    assert "23 147 963" not in masked
    assert "[PHONE]" in masked


def test_mask_contact_info_masks_local_phone_on_the_same_line_as_an_email() -> None:
    text = "jane.doe@example.com – 20 123 456"

    masked = mask_contact_info(text)

    assert "20 123 456" not in masked
    assert masked.count("[PHONE]") == 1


def test_mask_contact_info_masks_local_phone_after_an_explicit_label() -> None:
    text = "Tel: 20 123 456\nGSM: 55 987 654"

    masked = mask_contact_info(text)

    assert "20 123 456" not in masked
    assert "55 987 654" not in masked
    assert masked.count("[PHONE]") == 2


def test_mask_contact_info_does_not_mask_a_bare_number_with_a_thousands_separator() -> None:
    """Regression: found live against a real TDR fixture -- "16 500 jeunes"
    (a population figure, space as thousands separator) was wrongly masked
    as a phone number. A grouped-digit number is only trusted as a phone
    number on a line that also carries an email address or an explicit
    phone label (Tel/GSM/Mobile/Portable) -- this line has neither.
    """
    text = "A ces publics s'ajoutent 16 500 jeunes soit 1 sur 3"

    masked = mask_contact_info(text)

    assert masked == text


def test_mask_contact_info_does_not_mask_a_hyphenated_date_range() -> None:
    """Regression guard for the reverse failure mode: a hyphen-separated
    year/month range must never be treated as a phone separator (see
    mask_contact_info's docstring on why "-" is excluded).
    """
    text = "Expert DevOps, 2019-08 – présent"

    masked = mask_contact_info(text)

    assert masked == text


def test_mask_contact_info_does_not_mask_a_bare_graduation_year() -> None:
    text = "Diplôme d'ingénieur – SUP'COM, Tunis (2017)"

    masked = mask_contact_info(text)

    assert masked == text


def test_mask_cv_pii_detects_name_from_the_top_of_document_line() -> None:
    text = "Jane Doe\njane.doe@example.com – +216 23 147 963\nExpert DevOps"

    masked, name = mask_cv_pii(text)

    assert name == "Jane Doe"
    assert "[NOM]" in masked
    assert "Jane Doe" not in masked


def test_mask_cv_pii_detects_name_from_an_explicit_label() -> None:
    text = "Nom et Prénom: Karim Trabelsi\nArchitecte logiciel, 10 ans d'expérience"

    masked, name = mask_cv_pii(text)

    assert name == "Karim Trabelsi"
    assert "[NOM]" in masked


def test_mask_cv_pii_masks_every_occurrence_of_the_detected_name() -> None:
    text = "Jane Doe\nExpert DevOps\nRéférences: Jane Doe a mené ce projet"

    masked, name = mask_cv_pii(text)

    assert name == "Jane Doe"
    assert masked.count("[NOM]") == 2
    assert "Jane Doe" not in masked


def test_mask_cv_pii_returns_none_when_no_name_shaped_line_is_found() -> None:
    text = "curriculum vitae\nexpert devops, 7 ans d'expérience"

    masked, name = mask_cv_pii(text)

    assert name is None
    assert masked == text


def test_mask_cv_pii_detects_the_name_line_behind_a_job_title_headline() -> None:
    """Regression: found live -- a job-title headline before the name
    ("Chef De Projet Senior") used to win as "the name" under the old
    first-capitalized-line heuristic, leaking the real name ("Jane Doe")
    to the cloud LLM unmasked. The name line, directly above the
    email/phone line, must be preferred over the headline.
    """
    text = "Chef De Projet Senior\nJane Doe\njane.doe@example.com - +216 23 147 963"

    masked, name = mask_cv_pii(text)

    assert name == "Jane Doe"
    assert "[NOM]" in masked
    assert "Jane Doe" not in masked
    assert "Chef De Projet Senior" in masked


def test_mask_cv_pii_detects_the_name_line_above_a_labelled_phone_line() -> None:
    """Real-fixture-derived layout variant: name line, then a "Née le"
    date-of-birth line, then a role headline containing job-title words --
    the name must still be recovered from the line above the contact line,
    not from the headline further down.
    """
    text = (
        "Cheffe De Projet Senior\n"
        "Nadia Ben Salah\n"
        "nadia.bensalah@example.com - +216 20 123 456\n"
        "Née le: 12/04/1984\n"
        "Cheffe de projet SI avec 15 ans d'expérience"
    )

    masked, name = mask_cv_pii(text)

    assert name == "Nadia Ben Salah"
    assert "[NOM]" in masked
    assert "Nadia Ben Salah" not in masked


def test_mask_contact_info_masks_a_compact_phone_number_next_to_an_email() -> None:
    """Regression: found live -- a phone number written with no internal
    separator ("0555987654") was invisible to the old regexes, which
    required a separator between digit groups, and leaked unmasked right
    next to the email address.
    """
    text = "jane.doe@example.com - 0555987654"

    masked = mask_contact_info(text)

    assert "0555987654" not in masked
    assert masked.count("[PHONE]") == 1


def test_mask_contact_info_masks_a_compact_phone_number_with_country_code() -> None:
    text = "Contactez-moi au +21620123456"

    masked = mask_contact_info(text)

    assert "+21620123456" not in masked
    assert "[PHONE]" in masked


def test_mask_contact_info_does_not_mask_a_compact_number_without_email_or_label() -> None:
    """The compact-number gating must mirror the existing separated-number
    gating exactly: a bare 8-12 digit run with no email/label on the line
    is not trusted as a phone number, same as the "16 500 jeunes" case.
    """
    text = "Le projet a mobilisé un budget de 123456789 dinars"

    masked = mask_contact_info(text)

    assert masked == text
