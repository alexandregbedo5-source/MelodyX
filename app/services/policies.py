"""User-facing policy text that describes the current MELODYX implementation."""

from app.models.policies import POLICY_VERSION


POLICY_DOCUMENTS = {
    "privacy": {
        "title": "Politique de confidentialité",
        "eyebrow": "Données et transparence",
        "lead": (
            "Cette page explique quelles données l’instance MELODYX traite, pourquoi, "
            "qui peut les recevoir et combien de temps elles sont conservées."
        ),
        "sections": [
            {
                "heading": "Qui exploite ce service ?",
                "paragraphs": [
                    "Le responsable du traitement est l’exploitant de cette instance MELODYX. "
                    "L’identité juridique et l’adresse de contact ne sont pas encore renseignées dans cette version locale. "
                    "L’exploitant doit les compléter avant toute mise en ligne publique.",
                ],
            },
            {
                "heading": "Quelles données sont utilisées ?",
                "bullets": [
                    "Le fichier audio envoyé (ou enregistré au microphone), son nom, son empreinte technique, sa durée, son format, sa fréquence d’échantillonnage et le nombre de canaux.",
                    "Les données musicales produites par l’analyse : notes estimées, mesures, tempo, tonalité, accords, partition finale, exports et état de traitement.",
                    "Un identifiant de session anonyme dans le cookie melodyx_sid, pour retrouver la bibliothèque et compter les transcriptions.",
                    "La version des textes acceptés, les choix requis, le choix Gemini facultatif et l’heure d’acceptation, afin d’appliquer les préférences de la session.",
                    "L’état du forfait simulé. Cette démonstration ne demande ni numéro de carte bancaire ni identifiant Mobile Money.",
                ],
            },
            {
                "heading": "Pourquoi et où ces données sont-elles traitées ?",
                "paragraphs": [
                    "L’audio est traité par le serveur MELODYX pour calculer et afficher une partition, permettre son écoute et préparer ses exports. "
                    "La base SQLite et les fichiers sont conservés dans le stockage configuré pour l’instance.",
                    "Le transfert à Google Gemini est facultatif et désactivé par défaut. Si tu l’autorises, MELODYX transmet à Google les données musicales dérivées nécessaires au résumé ou à une réponse pédagogique; le fichier audio original n’est pas envoyé à Gemini par le pipeline actuel. "
                    "Les conditions de Google varient selon le niveau gratuit ou payant du projet : pour les services gratuits, Google indique que les contenus peuvent servir à améliorer ses produits et que des personnes peuvent examiner certaines entrées et sorties. N’envoie pas de données confidentielles ou sensibles à Gemini.",
                    "Les polices d’affichage sont chargées depuis Google Fonts dans le navigateur. Le navigateur contacte donc ce fournisseur lors de l’affichage des pages.",
                ],
            },
            {
                "heading": "Combien de temps ?",
                "paragraphs": [
                    "Les fichiers audio, résultats, partitions et exports expirent après 24 heures selon la configuration actuelle; une tâche de nettoyage les supprime périodiquement. "
                    "La preuve d’acceptation et le choix Gemini restent associés à la session anonyme pendant 30 jours, puis expirent.",
                ],
            },
            {
                "heading": "Tes choix et tes droits",
                "paragraphs": [
                    "Les trois documents de la page précédente sont requis pour importer un morceau. L’autorisation Gemini est séparée, facultative et peut être activée ou désactivée depuis le studio. Sans cette autorisation, la transcription fonctionne sans résumé Gemini.",
                    "Tu peux demander l’accès, la rectification, l’opposition ou la suppression des données te concernant auprès de l’exploitant. Utilise l’adresse de contact ci-dessous lorsqu’elle aura été configurée; en attendant, l’analyse est automatiquement supprimée à l’expiration des 24 heures.",
                    "Cette instance locale ne comporte pas encore de formulaire autonome pour traiter les demandes de droits. Avant une mise en service publique, l’exploitant doit publier ses coordonnées, sécuriser l’hébergement et vérifier les formalités applicables auprès de l’APDP, notamment pour tout transfert international.",
                ],
            },
        ],
        "references": [
            {
                "label": "Code du numérique du Bénin — APDP (notamment information des personnes et transferts)",
                "url": "https://apiprod.apdp.bj/storage/c46ab3f55e93d40c8545b70add0ea8c7/CODE-DU-NUMERIQUE-DU-BENIN_2018-version-APDP.pdf",
            },
            {
                "label": "Outils et modèle de politique de confidentialité — APDP Bénin",
                "url": "https://archive.apdp.bj/les-outils-de-la-conformite/",
            },
            {
                "label": "Conditions et traitement des données de Gemini API — Google",
                "url": "https://ai.google.dev/gemini-api/terms",
            },
        ],
    },
    "copyright": {
        "title": "Politique de respect du droit d’auteur",
        "eyebrow": "Droits sur les œuvres musicales",
        "lead": (
            "N’importe quel morceau ne peut pas être utilisé librement parce qu’il est accessible en ligne. "
            "Cette règle s’applique à l’audio importé comme aux partitions exportées."
        ),
        "sections": [
            {
                "heading": "Avant d’importer",
                "bullets": [
                    "Importe uniquement un enregistrement que tu as créé, que tu es autorisé à utiliser, qui est couvert par une licence adaptée, ou qui est effectivement dans le domaine public.",
                    "L’accès à un morceau sur une plateforme de streaming, l’achat d’une copie ou la mention du nom de l’artiste ne confèrent pas automatiquement le droit de le téléverser ou de le transcrire.",
                    "Si l’audio contient une œuvre, une interprétation ou un enregistrement de tiers, obtiens les autorisations requises pour le traitement et l’usage que tu prévois.",
                ],
            },
            {
                "heading": "Traitement limité par MELODYX",
                "paragraphs": [
                    "L’import autorise le traitement technique temporaire nécessaire pour analyser l’audio, afficher la partition et fournir les exports demandés. Il ne transfère pas à MELODYX la propriété de l’œuvre et n’autorise pas sa republication par MELODYX.",
                    "La transcription produite est un résultat d’analyse. Son export, sa représentation publique, sa distribution ou son exploitation commerciale peuvent nécessiter des autorisations supplémentaires; vérifie les droits avant tout usage.",
                ],
            },
            {
                "heading": "Signalement",
                "paragraphs": [
                    "Si tu penses qu’un contenu a été importé ou utilisé sans autorisation, contacte l’exploitant de l’instance avec le titre de l’œuvre, la partie contestée et la manière de te joindre. Les coordonnées du responsable restent à configurer dans cette version locale.",
                ],
            },
        ],
        "references": [
            {
                "label": "Loi béninoise n° 2005-30 du 5 avril 2006 sur le droit d’auteur et les droits voisins — WIPO Lex",
                "url": "https://www.wipo.int/wipolex/fr/legislation/details/7585",
            },
        ],
    },
    "plagiarism": {
        "title": "Politique de non-plagiat",
        "eyebrow": "Création et attribution",
        "lead": (
            "MELODYX est un outil d’étude et de transcription. Il ne donne pas le droit de présenter le travail d’autrui comme le sien."
        ),
        "sections": [
            {
                "heading": "Usages interdits",
                "bullets": [
                    "Ne présente pas une composition, une interprétation, un arrangement ou une partition créés par quelqu’un d’autre comme ta propre création.",
                    "Ne retire pas volontairement les noms, crédits ou informations de droits pour masquer l’origine d’une œuvre.",
                    "N’utilise pas MELODYX pour contourner une licence, dissimuler une copie ou diffuser sans autorisation une œuvre protégée.",
                ],
            },
            {
                "heading": "Attribuer et vérifier",
                "bullets": [
                    "Lorsque tu partages une œuvre ou une transcription, indique l’auteur, le titre, l’interprète ou l’arrangeur lorsque ces informations sont connues et respecte la licence applicable.",
                    "Les transcriptions et suggestions peuvent contenir des erreurs ou ressembler à des œuvres existantes. MELODYX ne certifie ni l’originalité, ni l’absence de plagiat, ni la disponibilité juridique d’une partition.",
                    "Vérifie le résultat, les crédits et les droits avant de le publier, de le soumettre comme travail personnel ou de l’exploiter.",
                ],
            },
            {
                "heading": "Application",
                "paragraphs": [
                    "Cette règle d’usage ne constitue pas un détecteur automatique de plagiat. L’exploitant peut examiner un signalement et restreindre l’accès d’une session en cas d’usage abusif, sous réserve des moyens disponibles dans cette version.",
                ],
            },
        ],
        "references": [],
    },
}
