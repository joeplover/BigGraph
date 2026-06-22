from pathlib import Path


def test_knowledge_base_api_exposes_delete_call() -> None:
    source = Path("frontend/src/api/knowledgeBase.js").read_text(encoding="utf-8")

    assert "export function deleteKnowledgeBase" in source
    assert "request.delete(`/api/knowledge_bases/${kbId}`)" in source


def test_settings_drawer_restricts_delete_to_owner_and_revalidates_owner() -> None:
    source = Path("frontend/src/views/chat/SettingsDrawer.vue").read_text(encoding="utf-8")

    assert 'v-if="kb.is_owner"' in source
    assert "handleDeleteKb(kb)" in source
    assert "getKnowledgeBase(kb.id)" in source
    assert "detail.owner_id !== authStore.userInfo?.user_id" in source
    assert "deleteKnowledgeBase(kb.id)" in source
