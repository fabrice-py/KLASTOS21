"""
KLASTOS21 - point d'entree pour un deploiement Streamlit.

Pourquoi ce fichier existe
--------------------------
`streamlit run` n'ajoute a `sys.path` que le dossier du script lance, jamais
la racine du projet. C'est explicite dans sa source : `_fix_sys_path` dans
streamlit/web/bootstrap.py, et le meme geste dans
streamlit/runtime/scriptrunner/exec_code.py.

Lancer `klastos/app.py` directement met donc `klastos/` sur le chemin, et pas
la racine. Les quatorze lignes `from klastos import ...` en tete de `app.py`
levent alors ModuleNotFoundError, et l'interface ne demarre pas du tout.

En local la faute est invisible : le paquet est installe en mode editable
(`pip install -e .`), donc l'import est resolu par le site-packages et le
chemin n'a aucune importance. Sur une plateforme de deploiement, seul
`requirements.txt` est installe - le paquet du depot, non. Verifie dans un
clone neuf, Python isole de l'installation editable :

    sys.path[0] = klastos/   ->  ModuleNotFoundError: No module named 'klastos'
    sys.path[0] = racine     ->  import OK

Ce fichier est a la racine. Streamlit y place donc la racine sur le chemin,
et `klastos` s'importe depuis le depot lui-meme, qu'il soit installe ou non.

C'est aussi le nom que Streamlit Community Cloud propose par defaut comme
fichier principal.

`klastos ui` continue de lancer `klastos/app.py` sans passer par ici, et
reste correct : en local, l'installation editable rend les deux equivalents.
"""

from klastos.app import main

main()
