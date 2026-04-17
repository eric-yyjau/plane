# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.
from plane.app.views.external import (
    UnsplashEndpoint,
    GPTIntegrationEndpoint,
    WorkspaceGPTIntegrationEndpoint,
    WorkspaceAIChatEndpoint,
    WorkspaceGoogleMeetSummaryEndpoint,
)


urlpatterns = [
    path("unsplash/", UnsplashEndpoint.as_view(), name="unsplash"),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/ai-assistant/",
        GPTIntegrationEndpoint.as_view(),
        name="importer",
    ),
    path(
        "workspaces/<str:slug>/ai-assistant/",
        WorkspaceGPTIntegrationEndpoint.as_view(),
        name="importer",
    ),
    path(
        "workspaces/<str:slug>/ai-chat/",
        WorkspaceAIChatEndpoint.as_view(),
        name="workspace-ai-chat",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/google-meet-summary/",
        WorkspaceGoogleMeetSummaryEndpoint.as_view(),
        name="workspace-google-meet-summary",
    ),
]
