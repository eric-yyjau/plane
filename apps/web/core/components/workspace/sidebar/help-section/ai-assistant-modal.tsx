/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Bot, Send } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { AIService } from "@/services/ai.service";

type TChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

const aiService = new AIService();

export const AIAssistantModal = (props: Props) => {
  const { isOpen, onClose } = props;
  const { workspaceSlug, projectId } = useParams();

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<TChatMessage[]>([
    {
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
    const nextMessages: TChatMessage[] = [...messages, { role: "user", content: userMessage }];
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

        setMessages((prev) => [...prev, { role: "assistant", content: assistantMessage }]);
      })
      .catch(() => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "AI Assistant",
          message: "Could not process your request right now.",
        });
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  return (
    <ModalCore
      isOpen={isOpen}
      handleClose={onClose}
      position={EModalPosition.CENTER}
      width={EModalWidth.XL}
      className="h-[70vh]"
    >
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-2 border-b border-subtle p-4">
          <Bot className="h-4 w-4 text-secondary" />
          <h3 className="text-sm font-semibold text-primary">AI Assistant</h3>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`max-w-[85%] rounded-md px-3 py-2 text-sm whitespace-pre-wrap ${
                message.role === "user" ? "ml-auto bg-custom-primary-100/10 text-primary" : "bg-layer-2 text-secondary"
              }`}
            >
              {message.content}
            </div>
          ))}
          {isLoading && (
            <div className="max-w-[85%] rounded-md bg-layer-2 px-3 py-2 text-sm text-secondary">Thinking...</div>
          )}
        </div>

        <div className="border-t border-subtle p-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about event planning, status, or create tasks..."
              className="h-10 flex-1 rounded-md border border-subtle bg-layer-1 px-3 text-sm text-primary outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSend();
              }}
            />
            <Button variant="primary" size="md" onClick={handleSend} loading={isLoading} disabled={!input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </ModalCore>
  );
};
