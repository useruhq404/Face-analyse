"""Modèle du graphe d'intelligence : nœuds, liens et construction.

Le graphe mélange :
  * des entités **réelles** issues de la base locale (personnes consentantes,
    photos, recherches OSINT, outils) ;
  * un sous-graphe de **démonstration synthétique**, clairement étiqueté, pour
    illustrer les relations (organisations, domaines, documents, événements)
    même quand la base est vide.

Aucune donnée personnelle extérieure n'est inventée : les nœuds « démo » sont
fictifs et marqués comme tels.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class NodeType:
    PERSON = "person"
    PHOTO = "photo"
    QUERY = "query"
    SOURCE = "source"
    TOOL = "tool"
    ORG = "org"
    DOMAIN = "domain"
    DOCUMENT = "document"
    EVENT = "event"


#: Libellés lisibles + ordre de la légende.
TYPE_LABELS = {
    NodeType.PERSON: "Personne",
    NodeType.PHOTO: "Photo",
    NodeType.QUERY: "Recherche",
    NodeType.SOURCE: "Source",
    NodeType.TOOL: "Outil",
    NodeType.ORG: "Organisation",
    NodeType.DOMAIN: "Domaine",
    NodeType.DOCUMENT: "Document",
    NodeType.EVENT: "Événement",
}


@dataclass
class Node:
    id: str
    ntype: str
    label: str
    demo: bool = False
    meta: dict = field(default_factory=dict)


@dataclass
class Edge:
    src: str
    dst: str
    kind: str = ""


@dataclass
class Graph:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def add(self, node: Node) -> str:
        self.nodes.append(node)
        return node.id

    def link(self, src: str, dst: str, kind: str = "") -> None:
        self.edges.append(Edge(src, dst, kind))

    def neighbors(self, node_id: str) -> set[str]:
        out: set[str] = set()
        for e in self.edges:
            if e.src == node_id:
                out.add(e.dst)
            elif e.dst == node_id:
                out.add(e.src)
        return out

    def types_present(self) -> list[str]:
        seen = {n.ntype for n in self.nodes}
        return [t for t in TYPE_LABELS if t in seen]


def synthetic_demo() -> Graph:
    """Petit graphe fictif d'illustration (clairement étiqueté « démo »)."""
    g = Graph()

    def demo(nid, ntype, label, **meta):
        return g.add(Node(nid, ntype, label, demo=True, meta=meta))

    # Deux organisations fictives, leurs domaines, documents et un événement.
    org1 = demo("d_org1", NodeType.ORG, "ACME RESEARCH", secteur="R&D", pays="FR")
    org2 = demo("d_org2", NodeType.ORG, "NOVA LABS", secteur="Cyber", pays="BE")
    for d in ["acme-research.example", "acme-cloud.example"]:
        demo(f"d_dom_{d}", NodeType.DOMAIN, d, enregistré="2021")
        g.link(org1, f"d_dom_{d}", "possède")
    demo("d_dom_novalabs.example", NodeType.DOMAIN, "novalabs.example", enregistré="2019")
    g.link(org2, "d_dom_novalabs.example", "possède")
    demo("d_doc1", NodeType.DOCUMENT, "rapport_2024.pdf", type="PDF", pages=12)
    demo("d_doc2", NodeType.DOCUMENT, "communiqué.txt", type="TXT")
    g.link(org1, "d_doc1", "publie")
    g.link(org2, "d_doc2", "publie")
    demo("d_evt1", NodeType.EVENT, "Partenariat annoncé", date="2024-03")
    g.link(org1, "d_evt1", "impliqué")
    g.link(org2, "d_evt1", "impliqué")
    demo("d_src1", NodeType.SOURCE, "Registre public", fiabilité="élevée")
    g.link("d_dom_acme-research.example", "d_src1", "vérifié par")
    g.link("d_dom_novalabs.example", "d_src1", "vérifié par")
    demo("d_p1", NodeType.PERSON, "Identité synthétique #1", note="entraînement")
    g.link("d_p1", org1, "employé")
    return g


def build_graph(repo, include_demo: bool = True, max_history: int = 60) -> Graph:
    """Construit le graphe à partir de la base locale (+ démo facultative)."""
    g = Graph()
    try:
        people = repo.list_people()
    except Exception:  # noqa: BLE001 - robustesse : un graphe partiel vaut mieux qu'un plantage
        people = []
    for p in people:
        pid = g.add(Node(f"person_{p.id}", NodeType.PERSON, p.display_name or "(sans nom)",
                         meta={"photos": p.photo_count}))
        try:
            photos = repo.list_photos(p.id)
        except Exception:  # noqa: BLE001
            photos = []
        for ph in photos:
            phid = g.add(Node(f"photo_{ph.id}", NodeType.PHOTO, f"photo #{ph.id}",
                              meta={"qualité": round(ph.quality, 2)}))
            g.link(pid, phid, "référence")

    # Recherches OSINT et outils, depuis l'historique réel.
    try:
        history = repo.history(limit=max_history)
    except Exception:  # noqa: BLE001
        history = []
    source_hub = None
    for h in history:
        if h.module == "osint" and h.action == "search":
            qid = g.add(Node(f"query_{h.id}", NodeType.QUERY, h.summary[:40], meta={"date": str(h.timestamp)[:16]}))
            if source_hub is None:
                source_hub = g.add(Node("hub_osint", NodeType.SOURCE, "Sources publiques",
                                        meta={"nature": "API officielles"}))
            g.link(qid, source_hub, "interroge")
        elif h.module == "tools":
            g.add(Node(f"tool_{h.id}", NodeType.TOOL, h.summary[:40], meta={"date": str(h.timestamp)[:16]}))

    if include_demo:
        demo = synthetic_demo()
        g.nodes.extend(demo.nodes)
        g.edges.extend(demo.edges)
    return g
