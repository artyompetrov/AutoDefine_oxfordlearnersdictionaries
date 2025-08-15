ATTENTION!
Config structure have recently changed, if you updated the addon press Restore Defaults button.
I recommend to use default settings!
Fields are indexed starting from 0. Enable options below only if the corresponding fields exist in your note type.

* `USE_DEFAULT_TEMPLATE`: Use default template AutoDefineOxfordLearnersDictionary (preferred). It creates two card sides; remove the reverse card by editing the template in Anki.
* `SOURCE_FIELD`: Index of field with defining word
* `CLEAN_HTML_IN_SOURCE_FIELD`: Remove html tags from source field
* `DEFINITION`: Add definition to DEFINITION_FIELD
* `DEFINITION_FIELD`: Index of field to insert definitions into
* `REPLACE_BY`: Replace learning words in examples (use $ sign to insert replacing word itself)
* `MAX_EXAMPLES_COUNT_PER_DEFINITION`: Maximum example count per definition ('false' for unlimited, or a number)
* `MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH`: Maximum definition count per part of speech ('false' for unlimited, or a number)
* `CORPUS`: 'American' or 'British' English; 'American_first' or 'British_first' will retrieve both corpora with the chosen one first.
* `AUDIO`: Add audio of pronunciation to AUDIO_FIELD
* `AUDIO_FIELD`: Index of field to insert audio into
* `PHONETICS`: Add International Phonetic Alphabet to PHONETICS_FIELD (requires PHONETICS_FIELD)
* `PHONETICS_FIELD`: Index of field to insert phonetics into
* `OPEN_IMAGES_IN_BROWSER`: Open a browser tab with an image search for the same word?
* `SEARCH_APPEND`: Append phrase when searching for images
* `OPEN_IMAGES_IN_BROWSER_LINK`: Images search link, $ sign will be replaced by the defining word
* `IMAGE_FIELD`: Image field order number
* `VERB_FORMS`: Add irregular verb forms
* `VERB_FORMS_FIELD`: Irregular verb forms field
* `PRIMARY_SHORTCUT`: Keyboard shortcut to run default AutoDefine.

This configuration is designed for a single note type. If you use multiple note types, adjust the field indexes accordingly.
