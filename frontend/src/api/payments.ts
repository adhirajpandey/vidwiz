import apiClient from './client';

export interface CheckoutSessionRequest {
  product_id: string;
  quantity?: number;
}

export interface CheckoutSessionResponse {
  checkout_url: string;
  session_id: string;
}

export const paymentsApi = {
  createCheckoutSession: async (payload: CheckoutSessionRequest) => {
    const response = await apiClient.post<CheckoutSessionResponse>(
      '/payments/checkout',
      payload
    );
    return response.data;
  },
};
