---
id: 2162
severity: "High"
---

# Users may lose value when transferring ERC-4626 Vault tokens cross-chain

## Description

** Both the `VaultV0` and `VaultV3` ERC-4626 tokens are designed to be transferable across chains and therefore implement the LayerZero cross-chain OFT standard.

When a token is transferred cross-chain, the `_debit` function is called to determine how the token should be "removed" from the source chain. The two standard approaches for this are **Lock/Unlock** and **Mint/Burn**. Both `VaultV0` and `VaultV3` implement the **Mint/Burn** approach, as seen in [`VaultV0::_debit` and `VaultV0::_credit`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/VaultV0.sol#L384-L393) (with an identical implementation in [`VaultV3`](https://github.com/d2sd2s/d2-contracts/blob/c2fc257605ebc725525028a5c17f30c74202010b/contracts/VaultV3.sol#L321-L330)):

```solidity
function _debit(address _from, uint256 _amountLD, uint256 _minAmountLD, uint32 _dstEid) internal virtual override returns (uint256 amountSentLD, uint256 amountReceivedLD) {
    (amountSentLD, amountReceivedLD) = _debitView(_amountLD, _minAmountLD, _dstEid);
    _burn(_from, amountSentLD);
}

function _credit(address _to, uint256 _amountLD, uint32) internal virtual override returns (uint256 amountReceivedLD) {
    if (_to == address(0x0)) _to = address(0xdead);
    _mint(_to, _amountLD);
    return _amountLD;
}
```

However, this approach is problematic for ERC-4626 vaults because `_burn` reduces the `totalSupply`. Since share value is calculated as `assets / totalSupply`, transferring tokens to another chain increases the share value of stakers who still have their tokens on the vault's original chain. This means that if these stakers withdraw, they will receive a portion of the assets that originally belonged to users who transferred their tokens cross-chain.

** Cross-chain transfers distort the vault’s share value. Users who transfer their tokens risk losing part or all of their value if other users withdraw while their tokens are still in transit.

## Proof of Concept

** The following test shows the issue, a similar test was written for `VaultV3`:
```solidity
function test_vaultV0_xchain_transfer_affects_vault_exchange_rate() public {
    deal(address(asset), DEPOSITOR, 2e18);

    // 1. Bob and Alice both participate in the vault
    vm.startPrank(DEPOSITOR);
    asset.approve(address(vault), 2e18);
    vault.deposit(1e18, ALICE);
    vault.deposit(1e18, BOB);
    assertEq(vault.balanceOf(ALICE), 1e18);
    assertEq(vault.balanceOf(BOB), 1e18);
    vm.stopPrank();

    // 2. Share price is not 1 to 1
    assertEq(vault.previewRedeem(1e18), 1e18);

    SendParam memory sendParam;
    sendParam.to = bytes32(uint256(1));
    sendParam.amountLD = 1e18;

    MessagingFee memory fee;

    // 3. Bob transfers his share to another chain
    vm.prank(BOB);
    vault.send(sendParam, fee, BOB);

    // Since the share is burnt on the source chain, share price has increased
    assertEq(vault.previewRedeem(1e18), 2e18);

    // 4. Alice redeems her share, getting Bobs share as well
    vm.prank(ALICE);
    vault.redeem(1e18,ALICE, ALICE);

    assertEq(vault.balanceOf(ALICE), 0);
    assertEq(asset.balanceOf(ALICE), 2e18);

    Origin memory origin;
    origin.sender = bytes32(uint256(1));
    (bytes memory message,) = OFTMsgCodec.encode(
        bytes32(uint256(uint160(BOB))),
        1e6,
        ""
    );

    // 5. Bob transfers back
    vm.prank(LZ_ENDPOINT);
    vault.lzReceive(
        origin,
        bytes32(uint256(0)),
        message,
        LZ_ENDPOINT,
        ""
    );

    // Bobs share is now worth nothing as Alice has redeemed it
    assertEq(vault.balanceOf(BOB), 1e18);
    assertEq(vault.previewRedeem(1e18), 0);

    vm.prank(BOB);
    vm.expectRevert("ZERO_ASSETS");
    vault.redeem(1e18, BOB, BOB);
}
```

## Recommendation

No recommendation

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a share‑value distortion that occurs when ERC‑4626 vault tokens are transferred across chains using the Mint/Burn pattern required by the LayerZero OFT standard. In this design the _debit function burns the sender’s shares on the source chain, which reduces the vault’s totalSupply while the underlying assets remain locked in the contract. Because ERC‑4626 defines the value of each share as assets divided by totalSupply, the reduction of totalSupply inflates the exchange rate for the remaining shares. Consequently, any user who keeps their tokens on the original chain sees a higher previewRedeem amount, but that increase is artificial: the extra value actually belongs to the shares that were burned and are still in transit. If another participant withdraws during this window, they receive a portion of the assets that should have been claimable by the transferred user. When the burned shares are later minted on the destination chain, the recipient finds that their shares are worth zero assets because the underlying pool has already been depleted. The impact is that users who initiate a cross‑chain transfer can lose part or all of their deposited value, and the protocol’s accounting invariants are broken, leading to potential fund loss and loss of trust. The issue manifests only while a transfer is pending; it is hard to notice because the share price appears to increase, which may be interpreted as a positive gain. The flaw was discovered during a security audit by observing that the previewRedeem value changes after a send call and that a later redeem by the original holder reverts with ZERO_ASSETS. To remediate, the vault should avoid burning shares for cross‑chain moves—using a lock/unlock mechanism that keeps totalSupply constant—or adjust the accounting to preserve the assets‑per‑share ratio during transit. This class of bug belongs to the broader category of accounting distortion in tokenized vaults caused by improper handling of share supply during cross‑chain operations.
