---
id: 16870
severity: "High"
---

# Griefing attack on the Vaults is possible, withdrawing the winning side stakes

## Description

_Anyone_ can withdraw to `receiver` once the `receiver` is `isApprovedForAll(owner, receiver)`. The funds will be sent to `receiver`, but it will happen whenever an arbitrary `msg.sender` wants. The only precondition is the presence of any approvals.

This can be easily used to sabotage the system as a whole. Say there are two depositors in the hedge Vault, Bob and David, both trust each other and approved each other. Mike the attacker observing the coming end of epoch where no depeg happened, calls the `withdraw()` for both Bob and David in the last block of the epoch. Mike gained nothing, while both Bob and David lost the payoff that was guaranteed for them at this point.

Setting the severity to be high as this can be routinely used to sabotage the Y2K users, both risk and hedge, depriving them from the payouts whenever they happen to be on the winning side. Usual attackers here can be the users from another side, risk users attacking hedge vault, and vice versa.

## Proof of Concept

`isApprovedForAll()` in withdrawal functions checks the `receiver` to be approved, not the caller.

SemiFungibleVault’s withdraw:

```solidity
function withdraw(
    uint256 id,
    uint256 assets,
    address receiver,
    address owner
) external virtual returns (uint256 shares) {
    require(
        msg.sender == owner || isApprovedForAll(owner, receiver),
        "Only owner can withdraw, or owner has approved receiver for all"
    );
```

Vault’s withdraw:

```solidity
function withdraw(
    uint256 id,
    uint256 assets,
    address receiver,
    address owner
)
    external
    override
    epochHasEnded(id)
    marketExists(id)
    returns (uint256 shares)
{
    if(
        msg.sender != owner &&
        isApprovedForAll(owner, receiver) == false)
        revert OwnerDidNotAuthorize(msg.sender, owner);
```

This way anyone at any time can run withdraw from the Vaults whenever owner has some address approved.

## Recommendation

Consider changing the approval requirement to be for the caller, not receiver:

SemiFungibleVault’s withdraw:

```solidity
function withdraw(
    uint256 id,
    uint256 assets,
    address receiver,
    address owner
) external virtual returns (uint256 shares) {
    require(
        msg.sender == owner || isApprovedForAll(owner, msg.sender),
        "Only owner can withdraw, or owner has approved receiver for all"
    );
```

Vault’s withdraw:

```solidity
function withdraw(
    uint256 id,
    uint256 assets,
    address receiver,
    address owner
)
    external
    override
    epochHasEnded(id)
    marketExists(id)
    returns (uint256 shares)
{
    if(
        msg.sender != owner &&
        isApprovedForAll(owner, msg.sender) == false)
        revert OwnerDidNotAuthorize(msg.sender, owner);
```

Implementing this.

Agree with the warden’s finding, and the impact of “depriving them (y2k users) from the payouts whenever they happen to be on the winning side”.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an improper authorization check in the withdrawal functions of both the SemiFungibleVault and the generic Vault contracts. Instead of verifying that the caller (msg.sender) is authorized to move the assets, the code validates that the *receiver* address has been approved for all tokens of the owner via isApprovedForAll(owner, receiver). Because many users grant each other universal approval to simplify interactions, the condition can be satisfied for any pair of mutually trusted participants. Consequently, any external account can invoke withdraw() on behalf of another user as long as the target receiver is an address that the owner has approved. This logical flaw allows a malicious actor to trigger withdrawals at a moment of their choosing—typically the final block of an epoch—causing the funds that were supposed to be paid out to the rightful depositor to be transferred to a receiver under the attacker’s control or to an address that nullifies the payout. The attack does not require the attacker to own the deposited assets; it only requires the existence of at least one approval relationship, which is common in the protocol where hedge and risk participants approve each other to streamline operations. When the epoch ends and the vault calculates the winning side’s payoff, the attacker can call withdraw() for each victim, bypassing the intended owner‑only restriction. The result is that the victims see no payout; their balances appear unchanged in the UI while the expected reward is missing, effectively sabotaging the protocol’s accounting and breaking the economic guarantee that the winning side receives its share. The issue was discovered during a formal audit where the withdrawal path was examined for proper access control. It is hard to notice because the approval check superficially appears to protect the transfer, yet it validates the wrong party, and the code pattern resembles common ERC‑1155 operator approvals, leading developers to assume it is safe. To remediate, the contract should require that the caller is either the owner or an address that the owner has explicitly approved (msg.sender), rather than checking the receiver. This aligns the access control with the intended security model: only authorized callers may initiate a withdrawal, and the receiver address can be any address the caller chooses. The bug belongs to the class of "incorrect authority validation" or "authorization bypass via mis‑parameter" vulnerabilities, which subvert business logic by allowing unintended parties to trigger state‑changing operations, resulting in loss of funds, broken payouts, and erosion of trust in the protocol.
