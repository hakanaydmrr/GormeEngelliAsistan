import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from conversation.router import IntentRouter
from conversation.spatial_memory import SpatialMemoryStore


class TestIntentRouter(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_yataga_git_hedef_cikarimi(self):
        route = self.router.route("Yatağa git")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Yatak")
        self.assertGreaterEqual(route.confidence, 0.99)

    def test_lavaboya_gotur_hedef_cikarimi(self):
        route = self.router.route("Lavaboya götür")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Lavabo")

    def test_buzdolabina_git_hedef_cikarimi(self):
        route = self.router.route("Buzdolabına git")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Buzdolabi")

    def test_firina_yonlendir_hedef_cikarimi(self):
        route = self.router.route("Fırına yönlendir")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Firin")

    def test_televizyona_git_hedef_cikarimi(self):
        route = self.router.route("Televizyona git")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Televizyon")

    def test_yemek_masasina_yonlendirme_hedef_cikarimi(self):
        route = self.router.route("Yemek masasına yönlendir")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "YemekMasasi")

    def test_onumde_ne_var_hedef_yok(self):
        route = self.router.route("Şu an önümde ne var")
        self.assertEqual(route.intent, "vision")
        self.assertIsNone(route.target)

    def test_internet_search_intentinde_hedef_yok(self):
        route = self.router.route("internetten altın fiyatına bak")
        self.assertEqual(route.intent, "internet_search")
        self.assertIsNone(route.target)

    def test_spatial_memory_hedef_cikarimi(self):
        spatial_store = SpatialMemoryStore()
        spatial_store.known_rooms = {
            "Mutfak": ["buzdolabı", "fırın", "lavabo"],
            "Yatak Odası": ["yatak", "komodin", "ayna"],
        }
        router = IntentRouter(spatial_store=spatial_store)
        route = router.route("Buzdolabıya git")
        self.assertEqual(route.intent, "vision")
        self.assertEqual(route.target, "Buzdolabı")


if __name__ == "__main__":
    unittest.main()
