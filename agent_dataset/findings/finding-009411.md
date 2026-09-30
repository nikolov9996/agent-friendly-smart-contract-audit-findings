---
id: 9411
severity: "High"
---

# A malicious actor can prevent sending messages through the executor and

## Description

The Executor program has an acl that is checked against when calling
quote :
```solidity
impl Quote<'_> {
    pub fn apply(
        ctx: &Context<Quote>, 
        params: &QuoteExecutorParams
    ) -> Result<u64> {
        require!(!ctx.accounts.executor_config.paused, ExecutorError::Paused);
        let config = &ctx.accounts.executor_config;
        config.acl.assert_permission(&params.sender)?;
    }
}
```
The permission is revoked through the SetDenylist function. The function
allows the caller to set addresses that will be included in the deny_list acl.
```solidity
#[derive(Accounts)]
pub struct SetDenylist<'info> {
    pub owner: Signer<'info>,
    #[account(
        seeds = [EXECUTOR_CONFIG_SEED],
        bump = config.bump
    )]
    pub config: Account<'info, ExecutorConfig>,
}
impl SetDenylist<'_> {
    pub fn apply(
        ctx: &mut Context<SetDenylist>,
        params: &SetDenylistParams
    ) -> Result<()> {
        for i in 0..params.denylist.len() {
            ctx.accounts.config.acl.set_denylist(&params.denylist[i])?;
        }
        Ok(())
    }
}
```
Notice that there is no access control and any user can call this function. A
malicious actor can prevent access to any sender (OApp) that is used to call
the executor quote function.
Currently, the ULN calls the quote function when paying the executor for a
send .
```solidity
fn pay_executor<'c: 'info, 'info>(
    uln: &Pubkey,
    payer: &AccountInfo<'info>,
    executor_config: &ExecutorConfig,
    dst_eid: u32,
    sender: &Pubkey,
    calldata_size: u64,
    options: Vec<LzOption>,
    accounts: &[AccountInfo<'info>], /* [executor_program, executor_config, price_feed_config] */
) -> Result<WorkerFee> {
    let fee = quote_executor(
        executor_config,
        dst_eid,
        sender,
        calldata_size,
        options,
        accounts
    );
--------------
```
Therefore, a malicious actor can prevent execution through the ULN as long as
they keep the deny list updated

## Proof of Concept

No poc.

## Recommendation

Consider adding to the config account:
```solidity
has_one = owner,
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unrestricted access control on the function that updates the deny‑list used by the executor’s access‑control list (ACL). The executor program checks the ACL before allowing a quote request, which is required for the Ultra Light Node (ULN) to calculate the fee and forward a cross‑chain message. The SetDenylist routine iterates over a caller‑supplied array and adds each address to the deny‑list, but it does not verify that the caller is the contract owner or any privileged role. Because there is no permission check, any external account can invoke this routine and insert arbitrary sender addresses – including the address of an OApp that the ULN relies on for quoting – into the deny‑list. When a sender is denied, the subsequent call to the quote function fails the ACL assertion, causing the executor to reject the fee quotation. The ULN, which automatically calls the quote function before paying the executor, then receives no fee estimate and aborts the send operation. This results in a denial‑of‑service condition where legitimate cross‑chain messages cannot be dispatched, effectively “blocking” the protocol’s messaging layer. The impact is that users or applications attempting to send messages experience silent failures: the UI may show no fee estimate, the transaction may revert with an ACL error, or the message simply never leaves the source chain, leading to funds being locked or delayed. The issue manifests whenever an attacker submits a SetDenylist transaction with the target sender’s address, and it persists as long as the deny‑list entry remains because only the contract owner can later remove it. The flaw was discovered during a manual audit of the executor’s permission checks, where the absence of a has_one or similar owner constraint on the SetDenylist instruction stood out as a logical oversight. It can be hard to notice because the function appears innocuous and the deny‑list is stored in a configuration account that is otherwise only read during normal operation; the failure only surfaces when a denied sender attempts to use the executor. To remediate, the SetDenylist instruction should enforce that only the designated owner (or another authorized role) can modify the deny‑list, for example by adding a has_one = owner constraint to the config account or by explicitly checking the caller’s signature against the stored owner address before mutating the ACL. This change restores the intended trust model, prevents arbitrary denial of service, and aligns the contract’s behavior with the business logic that only privileged entities may restrict message senders.
