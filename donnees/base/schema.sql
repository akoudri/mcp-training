-- Schéma de la base PHAROS (LAB 8 et suivants). Exécuté par « python -m donnees.base » sous le rôle
-- pharos_proprietaire, qui possède les tables et n'est jamais utilisé par un serveur.
-- Horodatages en timestamptz ; la base est réglée sur timezone = 'UTC' : une borne passée sans fuseau
-- est lue en UTC (piège du LAB 8, bloc 13.3). Les données sont en heure de Paris.

CREATE TABLE agents (
    agent_id text PRIMARY KEY,
    nom      text NOT NULL
);

CREATE TABLE navires (
    navire_id        text PRIMARY KEY,
    nom              text NOT NULL,
    imo              text NOT NULL,
    longueur_m       numeric(5, 1) NOT NULL,
    tirant_eau_max_m numeric(4, 1) NOT NULL,
    pavillon         text NOT NULL,
    agent_id         text NOT NULL REFERENCES agents
);

CREATE TABLE quais (
    quai             integer PRIMARY KEY,
    longueur_m       numeric(5, 1) NOT NULL,
    tirant_eau_max_m numeric(4, 1) NOT NULL,
    equipements      text[] NOT NULL,
    latitude         numeric(8, 5) NOT NULL,
    longitude        numeric(8, 5) NOT NULL
);

CREATE TABLE escales (
    escale_id     text PRIMARY KEY,
    navire_id     text NOT NULL REFERENCES navires,
    quai          integer NOT NULL REFERENCES quais,
    debut         timestamptz NOT NULL,
    fin           timestamptz NOT NULL,
    statut        text NOT NULL CHECK (statut IN ('prevue', 'accostee', 'terminee', 'annulee')),
    tirant_eau_m  numeric(4, 1) NOT NULL,
    tarif_negocie numeric(9, 2) NOT NULL,
    CHECK (debut < fin)
);

CREATE TABLE mouvements (
    mouvement_id   text PRIMARY KEY,
    escale_id      text NOT NULL REFERENCES escales,
    conteneur_id   text NOT NULL,
    sens           text NOT NULL CHECK (sens IN ('embarquement', 'debarquement')),
    horodatage     timestamptz NOT NULL,
    type_conteneur text NOT NULL CHECK (type_conteneur IN ('20', '40', 'refrigere'))
);

CREATE INDEX mouvements_horodatage ON mouvements (horodatage);
CREATE INDEX escales_quai_debut ON escales (quai, debut);

-- Table technique : doublons de la reprise de 2019. Aucun rôle applicatif ne la lit ; aucun outil ne
-- doit l'exposer (LAB 8).
CREATE TABLE esc_hdr_legacy (
    mouvement_id   text,
    escale_id      text,
    conteneur_id   text,
    sens           text,
    horodatage     timestamptz,
    type_conteneur text
);

-- Hors périmètre de tout outil : grilles tarifaires par navire (LAB 9, contournement 2).
CREATE TABLE tarifs (
    navire_id text PRIMARY KEY REFERENCES navires,
    grille    text NOT NULL,
    montant   numeric(9, 2) NOT NULL
);
