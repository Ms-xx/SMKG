/// <reference types="vite/client" />
import "axios";

declare module "axios" {
  interface AxiosRequestConfig {
    meta?: { silent?: boolean };
  }
}
