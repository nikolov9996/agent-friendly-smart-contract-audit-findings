---
id: 9244
severity: "Critical"
---

# Mint decimal manipulation through MintCloseAuthority leads to inflation of ld2sd_rate

## Description

The ld2sd_rate (local-to-shared decimal rate) can be manipulated by the initializer through the exploitation of the MintCloseAuthority extension in the Solana program. This manipulation is possible because the initializer has control over the mint’s decimal value, which can be changed after the mint’s creation, leading to critical discrepancies in token accounting and potential financial exploits.
The process to execute this exploit is as follows:
1. The admin creates a mint with an initial decimal value of 18 using the MintCloseAuthority extension, assigning the close authority to an address they control.
2. The admin uses the mint in the InitONFT, resulting in 1e12 as a value of the ld2sd_rate (assuming 6 shared decimals).
3. With the mint supply still at 0, the admin then uses the close authority to close the mint account.
4. After the mint is closed, the admin can reinitialize a new mint at the same address, but this time with a reduced decimal value, such as 6.
This manipulation of decimal values causes the ld2sd_rate to become inflated, as the program (ONFT) will still treat the mint as though it has 18 decimals while it actually operates with only 6 decimals. This mismatch leads to erroneous token calculations and can be used for various financial exploits.
Example Exploits:
• Legitimate transfers treated as dust:
Assume a token with a value of $1, where 1 token equals 1e6 units (decimal of 6). An admin or attacker can send 100,000 tokens (with a total value of $1,000,000). Using the manipulated ld2sd_rate, the program with an inflated rate of 1e12, causing the whole amount 1e11 (100 billion units) to dust due to remove_dust, meaning the tokens will not be sent as intended.
• Cross-chain Manipulation:
The attacker can initialize another ONFT_config with a different token escrow account, using the manipulated ld2sd_rate to transfer tokens from another chain (e.g., Ethereum) to Solana. The inflated rate on Solana causes the amount received to be much higher than intended. Once the tokens are transferred, the attacker switches the peer to the new ONFT_config using the correct (lower) rate and transfers the tokens back to the original chain, gaining an arbitrage-like advantage due to the discrepancy in the rates between the ONFT_config accounts.

```solidity
pub struct InitAdapterONft<'info> {
    [account(mut)]
    pub payer: Signer<'info>,
    [account(
        init,
        payer = payer,
        space = 8 + ONftConfig::INIT_SPACE,
        seeds = [ONft_SEED, token_escrow.key().as_ref()],
        bump
    )]
    pub ONft_config: Account<'info, ONftConfig>,
    [account(
        init,
        payer = payer,
        space = 8 + LzReceiveTypesAccounts::INIT_SPACE,
        seeds = [LZ_RECEIVE_TYPES_SEED, &ONft_config.key().as_ref()],
        bump
    )]
    pub lz_receive_types_accounts: Account<'info, LzReceiveTypesAccounts>,
    [account(mint::token_program = token_program)]
    pub token_mint: InterfaceAccount<'info, Mint>,
    [account(
        init,
        payer = payer,
        token::authority = ONft_config,
        token::mint = token_mint,
        token::token_program = token_program,
    )]
    pub token_escrow: InterfaceAccount<'info, TokenAccount>,
    pub token_program: Interface<'info, TokenInterface>,
    pub system_program: Program<'info, System>,
}

impl InitAdapterONft<_> {
    pub fn apply(ctx: &mut Context<InitAdapterONft>, params: &InitAdapterONftParams) -> Result<()> {
        ctx.accounts.ONft_config.bump = ctx.bumps.ONft_config;
        ctx.accounts.ONft_config.token_mint = ctx.accounts.token_mint.key();
        ctx.accounts.ONft_config.ext = ONftConfigExt::Adapter(ctx.accounts.token_escrow.key());
        ctx.accounts.ONft_config.token_program = ctx.accounts.token_program.key();
        ctx.accounts.lz_receive_types_accounts.ONft_config = ctx.accounts.ONft_config.key();
        ctx.accounts.lz_receive_types_accounts.token_mint = ctx.accounts.token_mint.key();
        let oapp_signer = ctx.accounts.ONft_config.key();
        ctx.accounts.ONft_config.init(
            params.endpoint_program,
            params.admin,
            params.shared_decimals,
            ctx.accounts.token_mint.decimals,
            ctx.remaining_accounts,
            oapp_signer,
        )
    }
}
```

## Proof of Concept

no poc

## Recommendation

To mitigate this issue, it is strongly recommended to:
1. Add a check in the InitOFT instruction to verify that the MintCloseAuthority extension is not enabled.
2. Ensure that the close authority for the mint is explicitly set to None during initialization.
This will prevent the exploitation of the MintCloseAuthority and ensure that the mint’s decimal value cannot be manipulated after its creation, thereby safeguarding the ld2sd_rate from being inflated.
Use this function upon onft_config creation to prevent the mint close authority extension:

```solidity
pub fn is_supported_mint(mint_account: &InterfaceAccount<Mint>) -> bool {
    let mint_info = mint_account.to_account_info();
    let mint_data = mint_info.data.borrow();
    let mint = StateWithExtensions::<spl_token_2022::state::Mint>::unpack(&mint_data).unwrap();
    let extensions = mint.get_extension_types().unwrap();
    for e in extensions {
        if e == ExtensionType::MintCloseAuthority {
            return false;
        }
    }
    true
}
```

Then revert if the mint extension is not supported:
```solidity
if !is_supported_mint(&ctx.accounts.mint) {
    return Err(Error::UnsupportedBaseMint.into());
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a decimal manipulation flaw that allows an initializer who controls the MintCloseAuthority extension of a Solana token mint to change the mint’s declared decimal precision after the mint has been created. The root cause is that the ONFT program stores the local‑to‑shared decimal rate (ld2sd_rate) based on the mint’s decimals at the moment of initialization and never updates it, while the mint itself can be closed and re‑initialized with a different decimal value when a close authority is present. An attacker can therefore create a mint with a high decimal count (for example 18), let the ONFT program compute an ld2sd_rate of 1e12 assuming six shared decimals, then close the mint and reopen it at the same address with a lower decimal count (for example 6). Because the program continues to treat the mint as if it still has 18 decimals, all subsequent token calculations use an inflated conversion factor. This mismatch leads to erroneous accounting: legitimate transfers may be classified as dust and removed, cross‑chain transfers can be over‑credited, and arbitrage opportunities arise when the attacker switches between ONFT configurations that use different rates. The exploit can be carried out whenever the mint is created with the MintCloseAuthority extension and the close authority is controlled by the attacker, the mint supply is still zero, and the ONFT configuration does not re‑validate the mint’s decimal precision after a close/re‑open cycle. Users experience symptoms such as receiving zero tokens when a transfer is expected, seeing their balances disappear after a dust‑removal step, or observing unexpectedly large amounts arriving from another chain. The issue is difficult to notice because the decimal value is not displayed in most user interfaces and the program’s internal rate appears correct, so the mis‑calculation only manifests in edge‑case operations. The flaw was discovered during a security audit that examined the initialization logic of the ONFT contract and identified that the MintCloseAuthority extension permits mutable token metadata. To remediate the problem, the protocol should forbid the MintCloseAuthority extension on any mint used by ONFT, enforce that the close authority is set to None at creation, and add an explicit check in the InitOFT instruction that validates the mint’s extensions and ensures the stored decimal count cannot be altered after initialization. This restores the invariant that the ld2sd_rate reflects the true token precision, preventing inflation of conversion rates and the associated financial exploits.
