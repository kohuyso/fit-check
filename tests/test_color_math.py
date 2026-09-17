from app.services.color_math import (
    hex_to_rgb,
    rgb_to_hex,
    rgb_to_cielab,
    calculate_delta_e_cie76,
    evaluate_color_compatibility,
    evaluate_outfit_palette_compatibility,
    get_color_name_from_hex,
    calculate_contrast_ratio,
    COLOR_GROUPS,
    COLOR_DICTIONARY,
    list_all_color_groups,
    get_color_group_from_hex,
    get_color_family_from_hex,
    get_color_tone_from_hex,
    get_color_details,
)

def test_hex_to_rgb_and_back():
    r, g, b = hex_to_rgb("#FFFFFF")
    assert (r, g, b) == (255, 255, 255)
    assert rgb_to_hex(r, g, b).upper() == "#FFFFFF"

    r0, g0, b0 = hex_to_rgb("#000000")
    assert (r0, g0, b0) == (0, 0, 0)
    assert rgb_to_hex(r0, g0, b0).upper() == "#000000"

def test_rgb_to_cielab():
    # Pure White
    l_val, a_val, b_val = rgb_to_cielab(255, 255, 255)
    assert round(l_val) == 100
    assert abs(a_val) < 2
    assert abs(b_val) < 2

    # Jet Black
    l_b, a_b, b_b = rgb_to_cielab(0, 0, 0)
    assert round(l_b) == 0

def test_calculate_delta_e_cie76():
    white_lab = rgb_to_cielab(255, 255, 255)
    black_lab = rgb_to_cielab(0, 0, 0)
    delta_e = calculate_delta_e_cie76(white_lab, black_lab)
    # White and Black should have a large delta E (~100)
    assert delta_e > 90

    # Identical colors
    assert calculate_delta_e_cie76(white_lab, white_lab) == 0.0

def test_get_color_name_from_hex():
    assert get_color_name_from_hex("#FFFFFF") == "Pure White"
    assert "Black" in get_color_name_from_hex("#000000")
    name = get_color_name_from_hex("#0A192F")
    assert len(name) > 0

def test_calculate_contrast_ratio():
    ratio = calculate_contrast_ratio("#FFFFFF", "#000000")
    assert ratio >= 20.0

def test_evaluate_color_compatibility():
    # Navy Blue and Gray
    res = evaluate_color_compatibility("#0A192F", "#64748B")
    assert "delta_e" in res
    assert "is_clashing" in res
    assert "lightness_difference" in res
    assert isinstance(res["is_clashing"], bool)

def test_evaluate_outfit_palette_compatibility():
    palette = ["#FFFFFF", "#000000", "#64748B"]
    analysis = evaluate_outfit_palette_compatibility(palette)
    assert "harmony_score" in analysis
    assert "harmony_type" in analysis
    assert "clashes" in analysis
    assert 0 <= analysis["harmony_score"] <= 100

def test_color_groups_structure():
    assert len(COLOR_GROUPS) == 20
    assert len(COLOR_DICTIONARY) > 200
    groups = list_all_color_groups()
    assert "Denim, Indigos & Sky Blues" in groups
    assert "Sages, Mints & Eucalyptus" in groups
    assert "Pastels & Soft Shades" in groups
    assert "Neons & Cyberpunk" in groups
    assert "Metallics & Shimmers" in groups

def test_get_color_group_and_family():
    # Denim Blue
    assert get_color_group_from_hex("#1C3144") == "Denim, Indigos & Sky Blues"
    assert get_color_family_from_hex("#1C3144") == "Blue"

    # Sage Green
    assert get_color_group_from_hex("#879B7F") == "Sages, Mints & Eucalyptus"
    assert get_color_family_from_hex("#879B7F") == "Green"

    # Neon Lime
    assert get_color_group_from_hex("#39FF14") == "Neons & Cyberpunk"
    assert get_color_family_from_hex("#39FF14") == "Neon"

    # Terracotta
    assert get_color_group_from_hex("#C2410C") == "Earth Tones, Terracottas & Rusts"
    assert get_color_family_from_hex("#C2410C") == "Brown"

def test_get_color_tone_from_hex():
    # Neutral (Black, White, Gray)
    assert get_color_tone_from_hex("#000000") == "Neutral"
    assert get_color_tone_from_hex("#FFFFFF") == "Neutral"
    assert get_color_tone_from_hex("#71717A") == "Neutral"

    # Warm (Red, Orange, Yellow)
    assert get_color_tone_from_hex("#DC2626") == "Warm"
    assert get_color_tone_from_hex("#F97316") == "Warm"
    assert get_color_tone_from_hex("#FACC15") == "Warm"

    # Cool (Royal Blue, Deep Navy)
    assert get_color_tone_from_hex("#2563EB") == "Cool"
    assert get_color_tone_from_hex("#1E3A8A") == "Cool"

def test_get_color_details():
    details = get_color_details("#3B82F6")
    assert details["hex"] == "#3B82F6"
    assert details["name"] == "Classic Blue"
    assert details["color_group"] == "Blues & Navies"
    assert details["color_family"] == "Blue"
    assert details["tone"] == "Cool"
    assert details["is_neutral"] is False
    assert "rgb" in details
    assert "cielab" in details


