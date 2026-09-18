export type PayMethod = {
  id: string;
  label: string;
  kind?: string;
  available: boolean;
  reason?: string;
};

export type PayRail = {
  enabled: boolean;
  chain_id: number;
  chain: string;
  token: string;
  token_address: string | null;
  decimals: number;
  pay_to: string | null;
  confirmations: number;
  invoice_ttl_minutes: number;
  late_grace_hours: number;
  explorer: string;
  fixture?: boolean;
  closed_reason?: string;
  methods?: PayMethod[];
  plans: Record<string, { name: string; price_usd: number; days: number; watches: number; runs: number }>;
};

export type Invoice = {
  id: string;
  number: string;
  status: "pending" | "paid" | "expired" | string;
  plan: string;
  plan_name: string;
  days: number;
  payment_method: string;
  payment_method_label: string;
  line_items: { description: string; qty: number; amount_usd: number; amount_usdc: string }[];
  amount_usd: number;
  chain_id: number;
  token: string;
  token_address: string;
  pay_to: string;
  amount_usdc: string;
  amount_raw: string;
  eip681: string;
  created_at?: string | null;
  expires_at: string | null;
  tx_hash: string | null;
  explorer_address: string;
  explorer_tx: string | null;
  confirmations_required: number;
  /** True once the quote has lapsed but a transfer can still buy the desk. */
  claimable: boolean;
  claim_deadline: string;
  late_grace_hours: number;
  late: boolean;
  public_path: string;
  desk_key: string | null;
  fixture?: boolean;
};

const BASE_CHAIN_ID = "0x2105";

export async function payWithWallet(invoice: Invoice): Promise<string> {
  const ethereum = (window as unknown as { ethereum?: { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> } })
    .ethereum;
  if (!ethereum) {
    throw new Error("No injected wallet. Use the address and exact USDC amount.");
  }
  const accounts = (await ethereum.request({ method: "eth_requestAccounts" })) as string[];
  const from = accounts?.[0];
  if (!from) throw new Error("Wallet returned no account.");
  try {
    await ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: BASE_CHAIN_ID }],
    });
  } catch (err) {
    const code = (err as { code?: number }).code;
    if (code === 4902) {
      await ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: BASE_CHAIN_ID,
            chainName: "Base",
            nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
            rpcUrls: ["https://mainnet.base.org"],
            blockExplorerUrls: ["https://basescan.org"],
          },
        ],
      });
    } else {
      throw err;
    }
  }
  const dest = invoice.pay_to.slice(2).toLowerCase().padStart(64, "0");
  const amount = BigInt(invoice.amount_raw).toString(16).padStart(64, "0");
  const data = `0xa9059cbb${dest}${amount}`;
  const tx = (await ethereum.request({
    method: "eth_sendTransaction",
    params: [{ from, to: invoice.token_address, data, chainId: BASE_CHAIN_ID }],
  })) as string;
  if (!tx) throw new Error("Wallet did not return a transaction hash.");
  return tx;
}
