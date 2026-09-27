-- Politique de cloisonnement de la base PHAROS (LAB 9, étape 3).
-- Appliquée sous le propriétaire des tables par « make lab9-politique », et de nouveau à chaque
-- « make lab8-base » : elle doit pouvoir se rejouer du début (DROP POLICY IF EXISTS avant chaque CREATE).
--
-- La base sait qui appelle par deux choses que le serveur pose à chaque transaction (perimetre.emprunter) :
--   SET LOCAL ROLE pharos_exploitation | pharos_agent
--   pharos.agent = 'AG-RANCE' | 'AG-IROISE' | ''   (lire : current_setting('pharos.agent', true))

ALTER TABLE escales ENABLE ROW LEVEL SECURITY;
ALTER TABLE mouvements ENABLE ROW LEVEL SECURITY;

-- L'exploitation et le moteur de planification (LAB 11) voient tout.
DROP POLICY IF EXISTS exploitation_escales ON escales;
CREATE POLICY exploitation_escales ON escales FOR SELECT TO pharos_exploitation, pharos_planification USING (true);
DROP POLICY IF EXISTS exploitation_mouvements ON mouvements;
CREATE POLICY exploitation_mouvements ON mouvements FOR SELECT TO pharos_exploitation, pharos_planification USING (true);

-- L'agent maritime ne voit que les escales de ses navires, et les mouvements de ces escales.
-- La sous-requête sur escales est elle-même filtrée par la politique : la RLS se compose.
DROP POLICY IF EXISTS agent_escales ON escales;
CREATE POLICY agent_escales ON escales FOR SELECT TO pharos_agent
    USING (navire_id IN (SELECT navire_id FROM navires WHERE agent_id = current_setting('pharos.agent', true)));
DROP POLICY IF EXISTS agent_mouvements ON mouvements;
CREATE POLICY agent_mouvements ON mouvements FOR SELECT TO pharos_agent
    USING (escale_id IN (SELECT escale_id FROM escales));
