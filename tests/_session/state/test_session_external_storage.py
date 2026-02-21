# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from inline_snapshot import snapshot

from marimo._data._external_storage.models import StorageNamespace
from marimo._messaging.notification import (
    StorageNamespacesNotification,
    VariableDeclarationNotification,
    VariablesNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t, VariableName

cell_id = CellId_t("cell_1")


def test_add_storage_namespaces(session_view: SessionView) -> None:
    # Add initial namespaces
    session_view.add_raw_notification(
        serialize_kernel_message(
            StorageNamespacesNotification(
                namespaces=[
                    StorageNamespace(
                        name=VariableName("s3_store"),
                        display_name="s3_store",
                        protocol="s3",
                        root_path="my-bucket",
                        storage_entries=[],
                    ),
                    StorageNamespace(
                        name=VariableName("local_fs"),
                        display_name="local_fs",
                        protocol="file",
                        root_path="/data",
                        storage_entries=[],
                    ),
                ]
            )
        )
    )

    assert session_view.external_storage_namespaces.namespaces == snapshot(
        [
            StorageNamespace(
                name=VariableName("s3_store"),
                display_name="s3_store",
                protocol="s3",
                root_path="my-bucket",
                storage_entries=[],
            ),
            StorageNamespace(
                name=VariableName("local_fs"),
                display_name="local_fs",
                protocol="file",
                root_path="/data",
                storage_entries=[],
            ),
        ]
    )

    # Add a new namespace and update an existing one
    session_view.add_raw_notification(
        serialize_kernel_message(
            StorageNamespacesNotification(
                namespaces=[
                    StorageNamespace(
                        name=VariableName("s3_store"),
                        display_name="s3_store_updated",
                        protocol="s3",
                        root_path="new-bucket",
                        storage_entries=[],
                    ),
                    StorageNamespace(
                        name=VariableName("gcs_store"),
                        display_name="gcs_store",
                        protocol="gcs",
                        root_path="gcs-bucket",
                        storage_entries=[],
                    ),
                ]
            )
        )
    )

    assert session_view.external_storage_namespaces.namespaces == snapshot(
        [
            StorageNamespace(
                name=VariableName("s3_store"),
                display_name="s3_store_updated",
                protocol="s3",
                root_path="new-bucket",
                storage_entries=[],
            ),
            StorageNamespace(
                name=VariableName("local_fs"),
                display_name="local_fs",
                protocol="file",
                root_path="/data",
                storage_entries=[],
            ),
            StorageNamespace(
                name=VariableName("gcs_store"),
                display_name="gcs_store",
                protocol="gcs",
                root_path="gcs-bucket",
                storage_entries=[],
            ),
        ]
    )
    ns_by_name = {
        ns.name: ns
        for ns in session_view.external_storage_namespaces.namespaces
    }
    # Updated
    assert (
        ns_by_name[VariableName("s3_store")].display_name == "s3_store_updated"
    )
    assert ns_by_name[VariableName("s3_store")].root_path == "new-bucket"

    # Check namespaces appear in notifications
    assert (
        session_view.external_storage_namespaces in session_view.notifications
    )


def test_storage_namespaces_filtered_by_variables(
    session_view: SessionView,
) -> None:
    # Add storage namespaces
    session_view.add_notification(
        StorageNamespacesNotification(
            namespaces=[
                StorageNamespace(
                    name=VariableName("s3_store"),
                    display_name="s3_store",
                    protocol="s3",
                    root_path="bucket-1",
                    storage_entries=[],
                ),
                StorageNamespace(
                    name=VariableName("gcs_store"),
                    display_name="gcs_store",
                    protocol="gcs",
                    root_path="bucket-2",
                    storage_entries=[],
                ),
            ]
        )
    )
    assert len(session_view.external_storage_namespaces.namespaces) == 2

    # Declare both variables in scope
    session_view.add_notification(
        VariablesNotification(
            variables=[
                VariableDeclarationNotification(
                    name="s3_store", declared_by=[cell_id], used_by=[]
                ),
                VariableDeclarationNotification(
                    name="gcs_store", declared_by=[cell_id], used_by=[]
                ),
            ]
        )
    )
    assert len(session_view.external_storage_namespaces.namespaces) == 2

    # Remove gcs_store from variables => only s3_store remains
    session_view.add_notification(
        VariablesNotification(
            variables=[
                VariableDeclarationNotification(
                    name="s3_store", declared_by=[cell_id], used_by=[]
                ),
            ]
        )
    )
    assert session_view.external_storage_namespaces.namespaces == snapshot(
        [
            StorageNamespace(
                name=VariableName("s3_store"),
                display_name="s3_store",
                protocol="s3",
                root_path="bucket-1",
                storage_entries=[],
            ),
        ]
    )

    # Remove all variables => no namespaces remain
    session_view.add_notification(VariablesNotification(variables=[]))
    assert session_view.external_storage_namespaces.namespaces == []


def test_storage_namespaces_empty_not_in_notifications(
    session_view: SessionView,
) -> None:
    """Empty storage namespaces should not appear in notifications."""
    assert session_view.external_storage_namespaces.namespaces == []
    storage_ops = [
        op
        for op in session_view.notifications
        if isinstance(op, StorageNamespacesNotification)
    ]
    assert len(storage_ops) == 0


def test_storage_namespaces_in_notifications(
    session_view: SessionView,
) -> None:
    """Non-empty storage namespaces should appear in notifications."""
    session_view.add_notification(
        StorageNamespacesNotification(
            namespaces=[
                StorageNamespace(
                    name=VariableName("store"),
                    display_name="store",
                    protocol="s3",
                    root_path="bucket",
                    storage_entries=[],
                ),
            ]
        )
    )
    storage_ops = [
        op
        for op in session_view.notifications
        if isinstance(op, StorageNamespacesNotification)
    ]
    assert storage_ops == snapshot(
        [
            StorageNamespacesNotification(
                namespaces=[
                    StorageNamespace(
                        name=VariableName("store"),
                        display_name="store",
                        protocol="s3",
                        root_path="bucket",
                        storage_entries=[],
                    ),
                ]
            )
        ]
    )
