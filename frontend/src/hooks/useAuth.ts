import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchMe, login as loginApi, logout as logoutApi, type Me } from '@/api/auth';

const ME_KEY = ['auth', 'me'] as const;

export function useMe() {
  return useQuery<Me, Error>({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: loginApi,
    onSuccess: () => {
      // login 後 /me を取り直す
      qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: logoutApi,
    onSuccess: () => {
      qc.setQueryData(ME_KEY, null);
      qc.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}
