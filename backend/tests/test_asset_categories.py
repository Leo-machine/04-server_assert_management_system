from tests.conftest import op_headers


def test_seeded_asset_category_tree(client):
    response = client.get("/api/asset-categories?tree=true", headers=op_headers(1))
    assert response.status_code == 200
    tree = response.json()
    assert [node["name"] for node in tree] == ["数字化类", "计量类", "调度类"]
    digital = tree[0]
    assert [node["name"] for node in digital["children"]] == [
        "服务器类",
        "交换机类",
        "存储设备类",
    ]
    server = digital["children"][0]
    assert server["children"][0]["business_category"] == "内存"
    assert len(server["children"]) == 8


def test_leader_can_manage_three_levels(client):
    headers = op_headers(1)
    root = client.post(
        "/api/asset-categories",
        headers=headers,
        json={"name": "输电类", "code": "TRANSMISSION"},
    )
    assert root.status_code == 200, root.text
    second = client.post(
        "/api/asset-categories",
        headers=headers,
        json={"name": "线路类", "parent_id": root.json()["id"]},
    )
    assert second.status_code == 200, second.text
    assert second.json()["code"].startswith("TRANSMISSION_")
    leaf = client.post(
        "/api/asset-categories",
        headers=headers,
        json={"name": "架空线路", "parent_id": second.json()["id"]},
    )
    assert leaf.status_code == 200, leaf.text
    updated = client.put(
        f'/api/asset-categories/{leaf.json()["id"]}',
        headers=headers,
        json={
            "name": "架空输电线路",
            "parent_id": second.json()["id"],
            "sort_order": 20,
            "enabled": False,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "架空输电线路"
    assert updated.json()["enabled"] is False
    deleted = client.delete(
        f'/api/asset-categories/{leaf.json()["id"]}', headers=headers
    )
    assert deleted.status_code == 200


def test_seeded_metering_and_dispatch_accept_level2_children(client):
    headers = op_headers(1)
    rows = client.get("/api/asset-categories", headers=headers).json()
    for root_name, child_name, code in (
        ("计量类", "智能电表类", "METERING_SMART_METER"),
        ("调度类", "保护设备类", "DISPATCH_PROTECTION"),
    ):
        root = next(row for row in rows if row["name"] == root_name)
        response = client.post(
            "/api/asset-categories",
            headers=headers,
            json={"name": child_name, "code": code, "parent_id": root["id"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["level"] == 2
        assert response.json()["parent_id"] == root["id"]


def test_category_rules_and_permissions(client):
    headers = op_headers(1)
    rows = client.get("/api/asset-categories", headers=headers).json()
    digital = next(row for row in rows if row["name"] == "数字化类")
    server = next(row for row in rows if row["name"] == "服务器类")
    memory = next(row for row in rows if row["name"] == "内存")

    duplicate = client.post(
        "/api/asset-categories", headers=headers, json={"name": "数字化类"}
    )
    assert duplicate.status_code == 400
    too_deep = client.post(
        "/api/asset-categories",
        headers=headers,
        json={"name": "四级目录", "parent_id": memory["id"]},
    )
    assert too_deep.status_code == 400
    has_children = client.delete(
        f'/api/asset-categories/{server["id"]}', headers=headers
    )
    assert has_children.status_code == 400
    invalid_mapping = client.post(
        "/api/asset-categories",
        headers=headers,
        json={
            "name": "错误映射",
            "parent_id": digital["id"],
            "business_category": "内存",
        },
    )
    assert invalid_mapping.status_code == 400

    non_leader = client.post(
        "/api/asset-categories",
        headers=op_headers(2),
        json={"name": "无权新增"},
    )
    assert non_leader.status_code == 403


def test_catalog_records_follow_level2_asset_scopes(client):
    headers = op_headers(1)
    tree = client.get("/api/asset-categories?tree=true", headers=headers).json()
    digital = next(node for node in tree if node["name"] == "数字化类")
    server = next(node for node in digital["children"] if node["name"] == "服务器类")

    brand = client.post(
        "/api/brands",
        headers=headers,
        json={"name": "目录测试品牌", "asset_category_ids": [server["id"]]},
    )
    assert brand.status_code == 200, brand.text
    assert brand.json()["asset_category_ids"] == [server["id"]]

    supplier = client.post(
        "/api/suppliers",
        headers=headers,
        json={"name": "目录测试供应商", "asset_category_ids": [server["id"]]},
    )
    assert supplier.status_code == 200, supplier.text
    assert supplier.json()["asset_category_ids"] == [server["id"]]

    model = client.post(
        "/api/part-models",
        headers=headers,
        json={
            "category": "服务器",
            "model_name": "目录测试服务器型号",
            "asset_category_id": server["id"],
            "spec": {
                "机型高度U": 2,
                "CPU插槽数": 2,
                "CPU型号": "测试CPU",
            },
        },
    )
    assert model.status_code == 200, model.text
    assert model.json()["asset_category_id"] == server["id"]

    invalid = client.post(
        "/api/suppliers",
        headers=headers,
        json={"name": "错误一级目录供应商", "asset_category_ids": [digital["id"]]},
    )
    assert invalid.status_code == 400
