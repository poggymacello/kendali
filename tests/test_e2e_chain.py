"""End-to-end on a private anvil devnet: agent -> policy -> vault, including the LLM path."""

import socket

import pytest

from kendali.agent import KendaliAgent, OwnerConsole
from kendali.chain import Chain
from kendali.config import Settings
from kendali.deploy import find_anvil, seed_devnet, start_anvil
from kendali.models import Action
from kendali.registry import Registry

pytestmark = pytest.mark.chain


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    try:
        find_anvil()
    except FileNotFoundError:
        pytest.skip("anvil not installed")
    port = _free_port()
    proc = start_anvil(port)
    s = Settings()
    s.rpc_url = f"http://127.0.0.1:{port}"
    s.network = "pytest"
    s.runs_dir = tmp_path_factory.mktemp("runs")
    chain = Chain(s, load=False)
    reg = Registry.load(s.data_dir)
    seed_devnet(chain, reg)
    yield s, chain, reg
    proc.terminate()


def test_pay_then_duplicate_then_bec(env, inbox):
    s, chain, reg = env
    agent = KendaliAgent(s, chain, None, reg)
    v002 = reg.vendors["V002"].wallet
    before = chain.usdc.functions.balanceOf(v002).call()
    r = agent.process_invoice(inbox / "inv-01-huaxin-HX-2026-1042.txt")
    assert r.decision.action == Action.EXECUTE and r.onchain == "AutoPaid"
    assert chain.usdc.functions.balanceOf(v002).call() - before == 540_000_000
    r2 = agent.process_invoice(inbox / "inv-06-huaxin-HX-2026-1042-duplicate.txt")
    assert r2.decision.action == Action.BLOCK
    r3 = agent.process_invoice(inbox / "inv-04-huaxin-HX-2026-1077-BEC.txt")
    assert r3.decision.action == Action.BLOCK and r3.onchain == "DecisionCommitted"
    assert agent.audit.verify(chain.onchain_decision_hashes())["ok"]


def test_maker_checker(env, inbox):
    s, chain, reg = env
    agent = KendaliAgent(s, chain, None, reg)
    r = agent.process_invoice(inbox / "inv-02-gayo-KTG-0915.txt")
    assert r.decision.action == Action.REQUEST_APPROVAL and r.proposal_id is not None
    OwnerConsole(chain, reg).approve(r.proposal_id)
    assert chain.proposals()[r.proposal_id]["status"] == "Executed"


def test_llm_path_on_chain(env, inbox, llm_settings):
    s, chain, reg = env
    s2 = Settings()
    s2.__dict__.update(s.__dict__)
    s2.llm_base_url, s2.llm_api_key, s2.llm_model = llm_settings.llm_base_url, "test", "fake-model"
    from kendali.llm import get_llm

    agent = KendaliAgent(s2, chain, get_llm(s2), reg, run_dir=s.runs_dir / "llm")
    r = agent.process_invoice(inbox / "inv-01-huaxin-HX-2026-1042.txt")
    assert r.decision.llm_used
    assert r.decision.action == Action.BLOCK  # already paid in the first test -> duplicate, decided with the LLM in the loop


from tests.test_llm import llm_settings  # noqa: E402,F401  (re-use the fake OpenAI server fixture)
