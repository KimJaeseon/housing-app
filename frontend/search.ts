export function normalizeSeoul(input: string) {
  const value = input.replace(/\s/g, '');
  return ['서울','서울시','서울특별시'].includes(value) ? {id:'seoul',label:'서울특별시',serverRegion:'서울특별시'} : null;
}
export const scenarios = {
  completed: '조사 완료 · 예시 공고 1건',
  partial: '일부 출처 확인 실패 · 확인된 예시 공고 1건',
  empty: '연결된 출처에서 확인된 공고가 없습니다',
  failed: '출처를 확인하지 못했습니다. 다시 시도해 주세요',
} as const;
