interface ChromeTab {
  id?: number;
  url?: string;
}

interface ChromeMessageSender {
  id?: string;
}

interface ChromeEvent<T extends (...args: never[]) => void> {
  addListener(callback: T): void;
}

declare namespace chrome {
  namespace tabs {
    function query(queryInfo: { active?: boolean; lastFocusedWindow?: boolean }): Promise<ChromeTab[]>;
    function create(createProperties: { url: string; active?: boolean }): Promise<ChromeTab>;
    function sendMessage<T = unknown>(tabId: number, message: unknown): Promise<T>;
  }
  namespace scripting {
    function executeScript<T>(details: {
      target: { tabId: number };
      func: () => T;
    }): Promise<Array<{ result?: T }>>;
    function executeScript(details: { target: { tabId: number }; files: string[] }): Promise<Array<{ result?: unknown }>>;
    function registerContentScripts(scripts: Array<{ id: string; matches: string[]; js: string[]; runAt?: "document_idle" }>): Promise<void>;
    function unregisterContentScripts(filter: { ids: string[] }): Promise<void>;
  }
  namespace permissions {
    function request(permissions: { origins: string[] }): Promise<boolean>;
    function remove(permissions: { origins: string[] }): Promise<boolean>;
  }
  namespace storage {
    namespace local {
      function get(keys?: string[]): Promise<Record<string, unknown>>;
      function set(items: Record<string, unknown>): Promise<void>;
      function remove(keys: string | string[]): Promise<void>;
    }
  }
  namespace runtime {
    const id: string;
    function getURL(path: string): string;
    const onInstalled: ChromeEvent<() => void> | undefined;
    const onMessage: ChromeEvent<(
      message: unknown,
      sender: ChromeMessageSender,
      sendResponse: (response: unknown) => void,
    ) => boolean | void>;
    function sendMessage<T = unknown>(message: unknown): Promise<T>;
    function openOptionsPage(): Promise<void>;
    const onStartup: ChromeEvent<() => void> | undefined;
  }
  namespace alarms {
    function create(name: string, alarmInfo: { delayInMinutes?: number; periodInMinutes?: number }): void;
    const onAlarm: ChromeEvent<(alarm: { name: string }) => void>;
  }
  namespace contextMenus {
    function create(properties: { id: string; title: string; contexts: string[] }): void;
    const onClicked: ChromeEvent<(info: { menuItemId: string; selectionText?: string }, tab?: ChromeTab) => void>;
  }
}
