"""
KLASTOS21 - Le mouvement du site vitrine.

POURQUOI UN SITE QUI BOUGE, ET OU IL NE DOIT PAS BOUGER
---------------------------------------------------------
Un site immobile se lit comme une plaquette. Mais l'animation gratuite -
la parallaxe, le texte qui glisse, le chiffre qui tourne pour rien - dit
l'inverse de ce que ce produit vend : la rigueur.

Le mouvement sert donc trois choses, et rien d'autre.

1. REVELER. Les sections apparaissent a l'approche, ce qui donne au
   lecteur le rythme d'une demonstration plutot que d'un mur.
2. COMPTER. Les chiffres s'incrementent une fois, a leur premiere
   apparition. Ils viennent du lot reel analyse pendant la mise au point.
3. REPONDRE. La console d'identifiabilite est le coeur : le visiteur coche
   les elements doses et voit, en temps reel, ce que son bulletin
   determinerait. Les reponses sortent du moteur, pre-calculees a la
   construction. Rien n'est approxime ici.

Tout est suspendu sous `prefers-reduced-motion`. Une personne qui a
desactive les animations voit la page complete, immediatement, sans
transition - et la console reste parfaitement utilisable.
"""

from __future__ import annotations

SCRIPT = r"""
(function () {
  'use strict';

  var SOBRE = window.matchMedia &&
              window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------------------------------------------------------------- nav
  // La barre se compacte des que la page defile : elle rend sa hauteur au
  // contenu sans jamais disparaitre, parce qu'un visiteur qui descend doit
  // pouvoir changer de page sans remonter.
  var nav = document.querySelector('.nav');
  if (nav) {
    var majNav = function () {
      nav.classList.toggle('nav-compacte', window.scrollY > 24);
    };
    majNav();
    window.addEventListener('scroll', majNav, { passive: true });
  }

  // ------------------------------------------------------------ reveler
  var aReveler = document.querySelectorAll('[data-reveler]');
  if (SOBRE || !('IntersectionObserver' in window)) {
    aReveler.forEach(function (n) { n.classList.add('vu'); });
  } else {
    var oeil = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (!e.isIntersecting) return;
        var n = e.target;
        // Le decalage se lit sur l'element : une grille se revele carte
        // apres carte, un paragraphe d'un seul tenant.
        var rang = parseInt(n.getAttribute('data-reveler'), 10) || 0;
        setTimeout(function () { n.classList.add('vu'); }, rang * 70);
        oeil.unobserve(n);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 });
    aReveler.forEach(function (n) { oeil.observe(n); });
  }

  // ----------------------------------------------------------- compteurs
  var compteurs = document.querySelectorAll('[data-compteur]');
  var animerCompteur = function (n) {
    var cible = parseFloat(n.getAttribute('data-compteur'));
    var dec = parseInt(n.getAttribute('data-decimales'), 10) || 0;
    var suffixe = n.getAttribute('data-suffixe') || '';
    if (SOBRE) {
      n.textContent = cible.toFixed(dec).replace('.', ',') + suffixe;
      return;
    }
    // LA VALEUR JUSTE N'EST JAMAIS DETRUITE AVANT D'ETRE REMPLACEE.
    //
    // La remise a zero se faisait ici, avant le premier appel. Si
    // `requestAnimationFrame` ne rendait jamais la main - onglet en
    // arriere-plan, economie d'energie, moteur sans tete - le compteur
    // restait fige sur « 0 ». Trois chiffres FAUX en tete d'un site qui
    // vend l'exactitude, et sans la moindre erreur pour le signaler.
    //
    // Le zero est donc pose DANS la premiere image, c'est-a-dire une fois
    // qu'on sait que l'animation tourne. Si elle ne tourne pas, le
    // contenu initial - la valeur finale - reste affiche.
    var debut = null, duree = 900;
    var pas = function (t) {
      if (debut === null) debut = t;
      var p = Math.min((t - debut) / duree, 1);
      // Sortie cubique : rapide d'abord, puis le chiffre se pose.
      var v = cible * (1 - Math.pow(1 - p, 3));
      n.textContent = v.toFixed(dec).replace('.', ',') + suffixe;
      if (p < 1) requestAnimationFrame(pas);
    };
    requestAnimationFrame(pas);
  };
  if (!('IntersectionObserver' in window)) {
    compteurs.forEach(animerCompteur);
  } else {
    var oeilC = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        animerCompteur(e.target);
        oeilC.unobserve(e.target);
      });
    }, { threshold: 0.6 });
    compteurs.forEach(function (n) { oeilC.observe(n); });
  }

  // --------------------------------------------------------- copie
  // POURQUOI CE BOUTON EXISTE.
  //
  // Un lien `mailto:` ne mene nulle part chez une grande partie des
  // visiteurs. Sur Windows 11, le gestionnaire pointe souvent sur
  // l'application Courrier, retiree du systeme : la commande associee est
  // VIDE, et le clic n'ouvre rien - sans message d'erreur. Meme chose
  // pour qui lit son courrier dans un navigateur sans avoir declare de
  // gestionnaire.
  //
  // Copier l'adresse ne suppose aucun logiciel. C'est le seul geste qui
  // marche partout.
  document.querySelectorAll('[data-copier]').forEach(function (b) {
    b.addEventListener('click', function () {
      var adresse = b.getAttribute('data-copier');
      var confirme = function () {
        var avant = b.textContent;
        b.textContent = b.getAttribute('data-copie') || avant;
        b.classList.add('bouton-copie-faite');
        setTimeout(function () {
          b.textContent = avant;
          b.classList.remove('bouton-copie-faite');
        }, 2200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(adresse).then(confirme, function () {});
        return;
      }
      // Repli pour les navigateurs sans presse-papiers moderne, et pour
      // les pages servies sans HTTPS, ou l'API est refusee.
      var z = document.createElement('textarea');
      z.value = adresse;
      z.setAttribute('readonly', '');
      z.style.position = 'absolute';
      z.style.left = '-9999px';
      document.body.appendChild(z);
      z.select();
      try { document.execCommand('copy'); confirme(); } catch (e) {}
      document.body.removeChild(z);
    });
  });

  // ------------------------------------------------------------- console
  // Le coeur de la page. Les reponses viennent de demo.json, lui-meme
  // produit par klastos.identifiability a la construction : ce que le
  // visiteur lit est ce que le moteur repond, pas une maquette.
  var racine = document.querySelector('[data-console]');
  if (!racine) return;

  var ETAT = null, CHOIX = null;

  var masque = function () {
    return ETAT.elements.map(function (e) {
      return CHOIX.has(e) ? '1' : '0';
    }).join('');
  };

  var rendre = function () {
    var m = masque();
    var r = ETAT.table[m];
    var nPhases = ETAT.phases.length;
    var vide = !r;

    var deg = vide ? nPhases : r.d;
    var rang = vide ? 0 : r.r;
    var masqueF = vide ? 0 : r.f;
    var nFermes = 0;
    for (var b = masqueF; b; b >>= 1) nFermes += b & 1;

    racine.querySelector('[data-sortie="rang"]').textContent = rang;
    racine.querySelector('[data-sortie="deg"]').textContent = deg;
    racine.querySelector('[data-sortie="dosees"]').textContent = CHOIX.size;
    racine.querySelector('[data-sortie="fermes"]').textContent = nFermes;

    var jauge = racine.querySelector('[data-jauge]');
    if (jauge) jauge.style.width = (100 * rang / nPhases).toFixed(1) + '%';

    racine.querySelectorAll('[data-phase]').forEach(function (n, i) {
      n.classList.toggle('phase-ferme', !!(masqueF & (1 << i)));
    });

    var verdict = racine.querySelector('[data-verdict]');
    if (verdict) {
      var cle = nFermes === 0 ? 'rien'
              : nFermes < nPhases / 2 ? 'partiel' : 'large';
      verdict.setAttribute('data-etat', cle);
      verdict.textContent = verdict.getAttribute('data-' + cle) || '';
    }
  };

  var basculer = function (bouton) {
    var e = bouton.getAttribute('data-element');
    if (CHOIX.has(e)) CHOIX.delete(e); else CHOIX.add(e);
    bouton.setAttribute('aria-pressed', CHOIX.has(e) ? 'true' : 'false');
    rendre();
  };

  // Les donnees sont EN LIGNE dans la page, pas chargees par reseau.
  // `fetch` sur un fichier local est bloque par la politique d'origine :
  // le site ouvert depuis un disque - ce que fait tout relecteur a qui on
  // envoie l'archive - voyait une console morte.
  var brut = document.getElementById('demo-donnees');
  (function (d) {
    if (!d) { racine.classList.add('console-indisponible'); return; }
    try {
      ETAT = JSON.parse(d.textContent);
      CHOIX = new Set(ETAT.depart);
      racine.querySelectorAll('[data-element]').forEach(function (b) {
        b.setAttribute('aria-pressed',
                       CHOIX.has(b.getAttribute('data-element')) ? 'true'
                                                                 : 'false');
        b.addEventListener('click', function () { basculer(b); });
      });
      var raz = racine.querySelector('[data-raz]');
      if (raz) raz.addEventListener('click', function () {
        CHOIX = new Set(ETAT.depart);
        racine.querySelectorAll('[data-element]').forEach(function (b) {
          b.setAttribute('aria-pressed',
                         CHOIX.has(b.getAttribute('data-element')) ? 'true'
                                                                   : 'false');
        });
        rendre();
      });
      var tout = racine.querySelector('[data-tout]');
      if (tout) tout.addEventListener('click', function () {
        CHOIX = new Set(ETAT.elements);
        racine.querySelectorAll('[data-element]').forEach(function (b) {
          b.setAttribute('aria-pressed', 'true');
        });
        rendre();
      });
      racine.classList.add('console-prete');
      rendre();
    } catch (err) {
      // Une console muette serait pire qu'une console absente : la page
      // dit ce qui manque plutot que de faire semblant.
      racine.classList.add('console-indisponible');
    }
  })(brut);
})();
"""


def _sans_commentaires(code: str) -> str:
    """
    Retire les lignes de commentaire avant livraison.

    Le script est insere DANS LES DOUZE PAGES, anglaises comprises. Mes
    commentaires sont en francais : ils partaient donc dans les pages
    anglaises, et le test de fuite de langue les a attrapes sur le mot
    « Copier l'adresse », present a la fois au catalogue et dans un
    commentaire.

    Seules les lignes ENTIEREMENT commentees sont retirees. Couper a
    partir d'un `//` trouve en milieu de ligne casserait toute URL - et,
    plus insidieux, toute division suivie d'une expression reguliere.
    """
    gardees = [l for l in code.splitlines() if not l.lstrip().startswith("//")]
    return "\n".join(gardees)


#: Version livree : sans commentaires, donc sans francais dans les pages
#: anglaises, et douze fois plus legere a l'echelle du site.
SCRIPT_LIVRE = _sans_commentaires(SCRIPT)


def script() -> str:
    """Le script du site, pret a inserer en fin de document."""
    return SCRIPT_LIVRE
