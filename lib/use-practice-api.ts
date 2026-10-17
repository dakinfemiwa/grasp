"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

/**
 * Calls a practiceApi function with the signed-in user's Clerk session token.
 * Usage: const withToken = useWithToken(); withToken(practiceApi.templates)
 */
export function useWithToken() {
  const { getToken } = useAuth();
  return useCallback(
    async <A extends unknown[], R>(
      fn: (token: string | null, ...args: A) => Promise<R>,
      ...args: A
    ): Promise<R> => fn(await getToken(), ...args),
    [getToken],
  );
}
