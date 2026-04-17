/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// helpers
import { API_BASE_URL } from "@plane/constants";
// plane web constants
import type { AI_EDITOR_TASKS } from "@/constants/ai";
// services
import { APIService } from "@/services/api.service";
// types
// FIXME:
// import { IGptResponse } from "@plane/types";
// helpers

export type TTaskPayload = {
  casual_score?: number;
  formal_score?: number;
  task: AI_EDITOR_TASKS;
  text_input: string;
};
export type TWorkspaceAIChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type TWorkspaceAIChatResponse = {
  reply: string;
  actions_executed: {
    type: string;
    issue_id?: string;
    project_id?: string;
    issue_identifier?: string;
    name?: string;
    title?: string;
    start_time?: string;
    end_time?: string;
    meet_link?: string;
    status?: string;
  }[];
};

export type TGoogleMeetSummaryResponse = {
  summary: string;
  actions_executed: {
    issue_id: string;
    project_id: string;
    issue_identifier: string;
    name: string;
  }[];
};

export class AIService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async createGoogleMeetSummary(
    workspaceSlug: string,
    projectId: string,
    data: { transcript: string }
  ): Promise<TGoogleMeetSummaryResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/google-meet-summary/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createGptTask(workspaceSlug: string, data: { prompt: string; task: string }): Promise<any> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai-assistant/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response;
      });
  }

  async performEditorTask(
    workspaceSlug: string,
    data: TTaskPayload
  ): Promise<{
    response: string;
  }> {
    return this.post(`/api/workspaces/${workspaceSlug}/rephrase-grammar/`, data)
      .then((res) => res?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async chatWithWorkspaceAssistant(
    workspaceSlug: string,
    data: {
      message: string;
      history: TWorkspaceAIChatMessage[];
      project_id?: string;
    }
  ): Promise<TWorkspaceAIChatResponse> {
    return this.post(`/api/workspaces/${workspaceSlug}/ai-chat/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
