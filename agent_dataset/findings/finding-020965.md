---
id: 20965
severity: "High"
---

# `V3Utils.execute`

## Description

When a user wants to use `V3Utils`, one of the flows stated by the protocol is as follows:

  * TX1: User calls `NPM.approve(V3Utils, tokenId)`.
  * TX2: User calls `V3Utils.execute()` with specific instructions.

Note that this can’t be done in one transaction since in TX1, the NPM has to be called directly by the EOA which owns the NFT. Thus, the `V3Utils.execute()` would have to be called in a subsequent transaction.

Now this is usually a safe design pattern, but the issue is that `V3Utils.execute()` does not validate the owner of the UniV3 Position NFT that is being handled. This allows anybody to provide arbitrary instructions and call `V3Utils.execute()` once the NFT has been approved in TX1.

A malicious actor provide instructions that include the following:

  1. `WhatToDo = WITHDRAW_AND_COLLECT_AND_SWAP`.
  2. `recipient = malicious_actor_address`.
  3. `liquidity = total_position_liquidity`.

This would collect all liquidity from the position that was approved, and send it to the malicious attacker who didn’t own the position.

## Proof of Concept

This foundry test demonstrates how an attacker can steal all the liquidity from a UniswapV3 position NFT that is approved to the V3Utils contract.

To run the PoC:

  1. Add the following foundry test to `test/integration/V3Utils.t.sol`.
  2. Run the command `forge test --via-ir --mt test_backRunApprovals_toStealAllFunds -vv` in the terminal.
```solidity
function test_backRunApprovals_toStealAllFunds() external {
    address attacker = makeAddr("attacker");

    uint256 daiBefore = DAI.balanceOf(attacker);
    uint256 usdcBefore = USDC.balanceOf(attacker);
    (,,,,,,, uint128 liquidityBefore,,,,) = NPM.positions(TEST_NFT_3);

    console.log("Attacker's DAI Balance Before: %e", daiBefore);
    console.log("Attacker's USDC Balance Before: %e", usdcBefore);
    console.log("Position #%s's liquidity Before: %e", TEST_NFT_3, liquidityBefore);

    // Malicious instructions used by attacker:
    V3Utils.Instructions memory bad_inst = V3Utils.Instructions(
        V3Utils.WhatToDo.WITHDRAW_AND_COLLECT_AND_SWAP,
        address(USDC), 0, 0, 0, 0, "", 0, 0, "", type(uint128).max, type(uint128).max, 0, 0, 0,
        liquidityBefore, // Attacker chooses to withdraw 100% of the position's liquidity
        0,
        0,
        block.timestamp,
        attacker, // Recipient address of tokens
        address(0),
        false,
        "",
        ""
    );

    // User approves V3Utils, planning to execute next
    vm.prank(TEST_NFT_3_ACCOUNT);
    NPM.approve(address(v3utils), TEST_NFT_3);
    
    console.log("\n--ATTACK OCCURS--\n");
    // User's approval gets back-ran
    vm.prank(attacker);
    v3utils.execute(TEST_NFT_3, bad_inst);
    
    uint256 daiAfter = DAI.balanceOf(attacker);
    uint256 usdcAfter = USDC.balanceOf(attacker);
    (,,,,,,, uint128 liquidityAfter,,,,) = NPM.positions(TEST_NFT_3);

    console.log("Attacker's DAI Balance After: %e", daiAfter);
    console.log("Attacker's USDC Balance After: %e", usdcAfter);
    console.log("Position #%s's liquidity After: %e", TEST_NFT_3, liquidityAfter);
}
```
Console output:
```
Ran 1 test for test/integration/V3Utils.t.sol:V3UtilsIntegrationTest
[PASS] test_backRunApprovals_toStealAllFunds() (gas: 351245)
Logs:
  Attacker's DAI Balance Before: 0e0
  Attacker's USDC Balance Before: 0e0
  Position #4660's liquidity Before: 1.2922419498089422291e19

--ATTACK OCCURS--

  Attacker's DAI Balance After: 4.2205702812280886591005e22
  Attacker's USDC Balance After: 3.5931648355e10
  Position #4660's liquidity After: 0e0

Test result: ok. 1 passed; 0 failed; 0 skipped; finished in 1.17s

Ran 1 test suite in 1.17s: 1 tests passed, 0 failed, 0 skipped (1 total tests)
```

## Recommendation

```solidity
function execute(uint256 tokenId, Instructions memory instructions) public returns (uint256 newTokenId) {
    
    address tokenOwner = nonfungiblePositionManager.ownerOf(tokenId);
    if (tokenOwner != msg.sender && tokenOwner != address(this)) {
        revert Unauthorized();
    }
    
    /* REST OF CODE */
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the V3Utils.execute function, which processes instructions for a Uniswap V3 position NFT without confirming that the caller actually owns the NFT being manipulated. The root cause is a missing ownership check; the contract only requires that the NFT has been approved for V3Utils, assuming that approval implicitly authorises any subsequent call. An attacker can exploit this by waiting for a legitimate user to approve their position NFT to V3Utils in a separate transaction, then back‑running a call to execute with malicious instructions that specify the WITHDRAW_AND_COLLECT_AND_SWAP action, set the recipient to the attacker’s address, and request the total liquidity of the position. Because the contract does not verify the tokenOwner against msg.sender, the malicious call succeeds, withdrawing all liquidity from the approved position and swapping it to tokens that are sent directly to the attacker. The impact is a complete loss of the user’s liquidity: the position’s liquidity drops to zero, the user’s wallet receives no tokens, and the attacker’s balances increase dramatically, as demonstrated by the Foundry proof‑of‑concept. This scenario occurs whenever a user approves V3Utils for their NFT and the contract is called later by any address; the flaw is triggered in the approval‑then‑execute flow, which is a common pattern for utility contracts. The affected parties are the NFT owners (liquidity providers), the protocol that relies on the integrity of position management, and any downstream users who expect their funds to remain safe. The issue was discovered during a Code4rena audit, where a test showed that an attacker could back‑run the approval transaction and steal all funds. The bug can be hard to notice because the approval step appears benign and the execute call does not revert; the loss manifests only after the position’s liquidity disappears, which may be attributed to a swap failure or market movement rather than an authorization flaw. To remediate, the execute function should retrieve the current owner of the tokenId via the NonfungiblePositionManager and require that the caller is either that owner or the contract itself, reverting otherwise. This adds proper access control and prevents arbitrary parties from issuing instructions on approved NFTs. In broader terms, the flaw is an instance of insufficient authorization checks, allowing a back‑run attack on an approved token and violating the fundamental accounting assumption that only the token holder can withdraw or modify the underlying liquidity. From a user’s perspective, after approving V3Utils they may later see their position’s liquidity become zero, receive no tokens, and wonder why their funds vanished, while the attacker’s wallet shows a sudden influx of assets.
