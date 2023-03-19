import pytest
from pytest_anki import AnkiSession
from unittest.mock import MagicMock
from pathlib import Path
import requests
import time

max_attempt = 10
connection_timeout = 10

config = \
    {
        "0. test mode": {
            "TEST_MODE": True
        },
        "1. word": {
            " 1. SOURCE_FIELD": 0,
            " 2. CLEAN_HTML_IN_SOURCE_FIELD": False
        },
        "2. definition": {
            " 1. DEFINITION": True,
            " 2. DEFINITION_FIELD": 1,
            " 3. REPLACE_BY": "____",
            " 4. MAX_EXAMPLES_COUNT_PER_DEFINITION": 3,
            " 5. MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH": 3
        },
        "3. audio and phonetics": {
            " 1. CORPUS": "American",
            " 2. AUDIO": True,
            " 3. AUDIO_FIELD": 2,
            " 4. PHONETICS": True,
            " 5. PHONETICS_FIELD": 3,
            " 6. AUDIO_FORMAT": "mp3"
        },
        "4. image": {
            " 1. OPEN_IMAGES_IN_BROWSER": False,
            " 2. SEARCH_APPEND": "",
            " 3. OPEN_IMAGES_IN_BROWSER_LINK": "https://www.google.com/search?q=$&tbm=isch&safe=off&tbs&hl=en&sa=X",
            " 4. or use this link instead": "https://www.istockphoto.com/search/2/image?phrase=$"
        },
        "5. shortcuts": {
            " 1. PRIMARY_SHORTCUT": "ctrl+alt+e"
        }
    }

editor = MagicMock()
editor.web = None
editor.note = MagicMock()

with open("test_data.txt") as file:
    words = [line.strip() for line in file]


@pytest.mark.parametrize("anki_session", [dict(load_profile=True)], indirect=True)
def test_my_addon(anki_session: AnkiSession):
    anki_session.create_addon_config("AutoDefineAddon", config, config)
    my_addon = anki_session.load_addon("AutoDefineAddon")
    with anki_session.deck_installed(Path(__file__).parent / 'sample_deck.apkg'):
        length = len(words)
        for i, word in enumerate(words):
            print(word, round(i / length * 100), '%')
            editor.note.fields = {0: word, 1: "", 2: "", 3: ""}
            attempt = 1
            connection_error = True
            while connection_error:
                assert attempt <= max_attempt
                connection_error = False
                try:
                    my_addon.autodefine.get_data(editor)
                except requests.exceptions.ConnectionError:
                    connection_error = True
                    attempt += 1
                    time.sleep(connection_timeout)

            result = editor.note.fields
            assert len(result[1]) > 0
            assert len(result[2]) > 0
            assert len(result[3]) > 0
            print(result)
