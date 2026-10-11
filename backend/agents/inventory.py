"""Inventory agent: stock on hand, vendors, lead times, and (draft) reorders."""

from backend.agents.base import AgentRole

INVENTORY = AgentRole(
    name="inventory",
    title="Inventory",
    description="Checks stock by SKU/size, finds the restock vendor and lead time, checks whether the vendor will ship, and drafts reorders.",
    prompt_file="inventory.md",
    mcp_tools=frozenset({
        "check_stock", "get_pricing", "list_vendors", "check_vendor_can_ship", "draft_vendor_reorder",
        "release_held_reorders",
    }),
)
