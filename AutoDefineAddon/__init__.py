try:
    from . import autodefine
except Exception as ex:
    raise Exception("\n\nATTENTION! Please create screenshot this error massage and open an issue on \n"
                    "https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries/issues \n"
                    "(you can find the clickable link on the add-on page) \n"
                    "so I could investigate the reason of error and fix it") from ex