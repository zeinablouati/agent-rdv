"""Amélioration : l'événement porte le nom du patient et le type (pas de motif médical)."""

from agent_rdv.agenda.formats import description_evenement, resume_evenement
from agent_rdv.agenda.local import AgendaLocal
from agent_rdv.agenda.registre import RegistrePatients
from agent_rdv.agenda.service import ServiceRendezVous

from conftest import Horloge, paris


def test_resume_contient_nom_prenom_et_type():
    assert resume_evenement("Zeineb", "Louati", "standard") == "Zeineb Louati – standard"


def test_description_contient_telephone_et_type_mais_pas_de_motif():
    desc = description_evenement("0612345678", "suivi")
    assert "0612345678" in desc and "suivi" in desc


class AgendaCapteur(AgendaLocal):
    """Agenda local qui mémorise le patient transmis, pour vérifier le câblage."""

    patient_recu = None

    def ajouter(self, debut, fin, type_consultation, patient_id, patient=None):
        self.patient_recu = patient
        return super().ajouter(debut, fin, type_consultation, patient_id, patient=patient)


def test_le_patient_est_transmis_a_l_agenda(regles):
    agenda = AgendaCapteur(fuseau=regles.fuseau)
    service = ServiceRendezVous(regles, agenda, RegistrePatients(), Horloge())
    service.reserver("standard", paris(2026, 10, 19, 9, 0), "Sara", "Ben Ali", "0612345678")
    assert agenda.patient_recu is not None
    assert agenda.patient_recu.prenom == "Sara"
    assert agenda.patient_recu.nom == "Ben Ali"