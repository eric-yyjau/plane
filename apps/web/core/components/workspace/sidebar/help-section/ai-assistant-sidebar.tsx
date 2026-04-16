/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Bot, Send, X } from "lucide-react";
import { observer } from "mobx-react";
// propel
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
// services
import { AIService } from "@/services/ai.service";
// hooks
import { useAppTheme } from "@/hooks/store/use-app-theme";
// helpers
import { cn } from "@plane/utils";
import { v4 as uuidv4 } from "uuid";

type TChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

const aiService = new AIService();

export const AIAssistantSidebar = observer(() => {
  const { workspaceSlug, projectId } = useParams();
  const { aiAssistantSidebarCollapsed, toggleAIAssistantSidebar } = useAppTheme();

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<TChatMessage[]>([
    {
      id: uuidv4(),
      role: "assistant",
      content: "Hi — I can help brainstorm events, check planning progress, and create tasks in Plane when you ask.",
    },
  ]);

  const assistantHistory = useMemo(
    () => messages.map((message) => ({ role: message.role, content: message.content })),
    [messages]
  );

  const handleSend = async () => {
    if (!workspaceSlug || !input.trim() || isLoading) return;

    const userMessage = input.trim();
    const nextMessages: TChatMessage[] = [...messages, { id: uuidv4(), role: "user", content: userMessage }];
    setMessages(nextMessages);
    setInput("");
    setIsLoading(true);

    await aiService
      .chatWithWorkspaceAssistant(workspaceSlug.toString(), {
        message: userMessage,
        history: assistantHistory,
        project_id: projectId?.toString(),
      })
      .then((response) => {
        let assistantMessage = response.reply;
        if (response.actions_executed?.length) {
          const createdIssues = response.actions_executed
            .map((action) => `• ${action.issue_identifier}: ${action.name}`)
            .join("\n");
          assistantMessage = `${assistantMessage}\n\nCreated issues:\n${createdIssues}`;
        }

        setMessages((prev) => [...prev, { id: uuidv4(), role: "assistant", content: assistantMessage }]);
        return response;
      })
      .catch(() => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "AI Assistant",
          message: "Could not process your request right now.",
        });
        return null;
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  if (aiAssistantSidebarCollapsed) return null;

  return (
    <div
      className={cn(
        "shadow-xl relative z-10 flex h-full w-80 flex-col border-l border-subtle bg-canvas transition-all duration-300 ease-in-out",
        "fixed top-0 right-0 lg:static"
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-subtle p-4">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-secondary" />
          <h3 className="text-sm font-semibold text-primary">AI Assistant</h3>
        </div>
        <button
          onClick={() => toggleAIAssistantSidebar(true)}
          className="rounded-md p-1 text-secondary hover:bg-layer-2"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="custom-scrollbar flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "text-xs shadow-sm max-w-[90%] rounded-md px-3 py-2 whitespace-pre-wrap",
              message.role === "user"
                ? "bg-custom-primary-100/10 border-custom-primary-100/20 ml-auto border text-primary"
                : "border border-subtle bg-layer-2 text-secondary"
            )}
          >
            {message.content}
          </div>
        ))}

        {isLoading && (
          <div className="text-xs max-w-[90%] rounded-md border border-subtle bg-layer-2 px-3 py-2 text-secondary italic">
            Thinking...
          </div>
        )}
      </div>

      <div className="border-t border-subtle bg-layer-1 p-3">
        <div className="flex flex-col gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about event planning..."
            className="text-xs focus:border-custom-primary-100 min-h-[80px] w-full resize-none rounded-md border border-subtle bg-canvas p-3 text-primary transition-colors outline-none"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <div className="flex justify-end">
            <Button variant="primary" size="sm" onClick={handleSend} loading={isLoading} disabled={!input.trim()}>
              <Send className="mr-2 h-3 w-3" />
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
});
