---
id: 9252
severity: "High"
---

# Denial of Service Risk Due to Frozen token_escrow in ONFT::Adapter

## Description

In the init_ONft instruction, the token_mint is set without validation, allowing the initialization of a token_mint with a freeze_authority. SPL tokens with a freeze authority can have their accounts frozen by the token issuer or an authorized entity, posing a risk to the functioning of the ONFT.

```solidity
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

If the token_escrow is frozen, it will be impossible to transfer the locked token to it, causing a Denial of Service (DoS) in the send instruction. This will render the ONFT unusable because token transfers to the token_escrow will revert at this point:

```solidity
match &ctx.accounts.ONft_config.ext {
    ONftConfigExt::Adapter(_) => {
        if let Some(escrow_acc) = &mut ctx.accounts.token_escrow {
            // lock
            token_interface::transfer_checked(
                CpiContext::new(
                    ctx.accounts.token_program.to_account_info(),
                    TransferChecked {
                        from: ctx.accounts.token_source.to_account_info(),
                        mint: ctx.accounts.token_mint.to_account_info(),
                        to: escrow_acc.to_account_info(),
                        authority: ctx.accounts.signer.to_account_info(),
                    },
                ),
                amount_sent_ld,
                ctx.accounts.token_mint.decimals,
            )?;
        } else {
            return Err(ONftError::InvalidTokenEscrow.into());
        }
    }
}
```

## Proof of Concept

no poc

## Recommendation

1. During ONFT initialization, check if the token_mint has a freeze_authority and return an error if detected.
2. If support for such tokens is necessary, display a warning on the UI to inform traders of the associated risks.
3. Keep in mind that major regulated stablecoins, such as USDC, have a freeze_authority for security reasons (e.g., preventing money laundering). If the protocol wishes to support USDC or similar tokens, implement an allowlist for trusted tokens while applying strict checks on others.
Add this check in the init_ONFT function to the mint account to prevent using tokens with freeze authority:
```solidity
if mint_account.freeze_authority.is_some() {
    return Err(Error::MintHasFreezeAuthority);
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

During the initialization of an ONFT that uses the Adapter pattern, the contract stores the address of a token mint without checking whether the mint has a freeze authority. SPL tokens can be configured with a freeze authority that allows the token issuer or an authorized account to freeze any token account, including the escrow account used by the ONFT to lock transferred tokens. If the escrow account is frozen, the subsequent call to token_interface::transfer_checked in the send instruction reverts, because the token program rejects transfers to a frozen destination. As a result, the ONFT becomes unable to lock new tokens, effectively causing a denial-of-service condition. The vulnerability is triggered when a token with a freeze authority is supplied during init_ONft, or when the freeze authority is exercised after deployment. Users attempting to send their tokens see a transaction failure, often reported as "InvalidTokenEscrow" or a generic revert, and their balances remain unchanged, contrary to the expectation that the token will be locked in the escrow. The issue was discovered during a security audit that examined the init_ONft logic and noticed the absence of any validation of the mint’s freeze_authority flag. Because freeze authority is an optional feature, developers may not anticipate that a token such as USDC, which deliberately includes a freeze authority for regulatory purposes, could be used to freeze the escrow and halt the protocol. The problem is hard to notice in normal operation because the token appears functional until the freeze is applied, at which point the failure manifests only when a transfer is attempted. The bug belongs to the class of token-freeze based denial-of-service vulnerabilities, where missing checks on token properties allow an external authority to render a critical contract function unusable. To remediate, the init_ONft function should explicitly verify that the supplied mint does not have a freeze authority and reject the initialization, or the protocol should maintain an allowlist of trusted tokens and display a clear UI warning when a token with freeze authority is used. If a freeze does occur, the locked tokens cannot be moved by the contract until the authority unfreezes the escrow, meaning funds may remain inaccessible for the duration of the freeze.
