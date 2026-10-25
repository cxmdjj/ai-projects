import { create } from 'zustand';
import type { TaskInfo, TaskStatus } from '../types/api';
import { rememberLatestTask } from '../utils/taskCache';

export interface TaskToolRun {
  key: string;
  toolName: string;
  status: 'running' | 'success';
  summary?: string;
}

interface TaskState {
  task: TaskInfo | null;
  activeTaskId: number | null;
  tools: TaskToolRun[];
  resultReady: boolean;
  resultId: number | null;
  lastError: string | null;
  recovering: boolean;

  beginTask: (taskId: number, conversationId: number) => void;
  applyTaskInfo: (info: TaskInfo) => void;
  prepareReplay: (info: TaskInfo) => void;
  updateStatus: (taskId: number, status: TaskStatus, currentStep: string) => void;
  addTool: (taskId: number, toolName: string) => void;
  finishTool: (taskId: number, toolName: string, summary: string) => void;
  applyError: (taskId: number, message: string) => void;
  markDone: (taskId: number, finishedAt?: string) => void;
  setResultReady: (taskId: number, resultId: number) => void;
  setRecovering: (recovering: boolean) => void;
  clear: () => void;
}

let toolSeq = 0;

export const useTaskStore = create<TaskState>((set, get) => ({
  task: null,
  activeTaskId: null,
  tools: [],
  resultReady: false,
  resultId: null,
  lastError: null,
  recovering: false,

  beginTask: (taskId, conversationId) => {
    rememberLatestTask(conversationId, taskId);
    set({
      task: {
        task_id: taskId,
        conversation_id: conversationId,
        task_status: 'queued',
        current_step: 'pending',
        input_text: '',
        started_at: null,
        finished_at: null,
        error_message: null,
      },
      activeTaskId: taskId,
      tools: [],
      resultReady: false,
      resultId: null,
      lastError: null,
      recovering: false,
    });
  },

  applyTaskInfo: (info) => {
    rememberLatestTask(info.conversation_id, info.task_id);
    set({
      task: info,
      activeTaskId: info.task_id,
      lastError: info.error_message,
    });
  },

  prepareReplay: (info) => {
    rememberLatestTask(info.conversation_id, info.task_id);
    set({
      task: info,
      activeTaskId: info.task_id,
      tools: [],
      resultReady: false,
      resultId: null,
      lastError: null,
      recovering: true,
    });
  },

  updateStatus: (taskId, status, currentStep) => {
    const current = get().task;
    if (!current || current.task_id !== taskId) return;
    set({
      task: {
        ...current,
        task_status: status,
        current_step: currentStep,
      },
    });
  },

  addTool: (taskId, toolName) => {
    if (get().activeTaskId !== null && get().activeTaskId !== taskId) return;
    toolSeq += 1;
    set((state) => ({
      tools: [
        ...state.tools,
        {
          key: `run-${taskId}-${Date.now()}-${toolSeq}`,
          toolName,
          status: 'running',
        },
      ],
    }));
  },

  finishTool: (taskId, toolName, summary) => {
    if (get().activeTaskId !== null && get().activeTaskId !== taskId) return;
    set((state) => {
      const tools = [...state.tools];
      let matched = false;
      for (let i = tools.length - 1; i >= 0; i -= 1) {
        if (tools[i].toolName === toolName && tools[i].status === 'running') {
          tools[i] = { ...tools[i], status: 'success', summary };
          matched = true;
          break;
        }
      }
      if (!matched) {
        toolSeq += 1;
        tools.push({
          key: `run-${taskId}-${Date.now()}-${toolSeq}`,
          toolName,
          status: 'success',
          summary,
        });
      }
      return { tools };
    });
  },

  applyError: (taskId, message) => {
    const current = get().task;
    if (!current || current.task_id !== taskId) {
      set({ lastError: message });
      return;
    }
    set({
      lastError: message,
      task: { ...current, error_message: message },
    });
  },

  markDone: (taskId, finishedAt) => {
    const current = get().task;
    if (!current || current.task_id !== taskId) return;
    set({
      task: {
        ...current,
        finished_at: finishedAt ?? current.finished_at ?? new Date().toISOString(),
      },
    });
  },

  setResultReady: (taskId, resultId) => {
    if (get().activeTaskId !== taskId) return;
    set({ resultReady: true, resultId });
  },

  setRecovering: (recovering) => set({ recovering }),

  clear: () =>
    set({
      task: null,
      activeTaskId: null,
      tools: [],
      resultReady: false,
      resultId: null,
      lastError: null,
      recovering: false,
    }),
}));
