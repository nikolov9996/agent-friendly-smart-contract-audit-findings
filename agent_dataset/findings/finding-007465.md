---
id: 7465
severity: "High"
---

# Owner of a bad ShortRecord can front-run flagShort calls AND liquidateSecondary and prevent liquidation

## Description

A shorter can keep an unhealthy short position open by minting an NFT of it and front-running attempts to liquidate it with a transfer of this NFT (which transfers the short position to the new owner).

A Short Record (SR) is a struct representing a short position that has been opened by a user.
It holds different information, such as how much collateral is backing the short, and how much debt it owes (this ratio is called Collateral Ratio or CR).
At any time, any user can flag someone's else SR as "dangerous", if its debt grows too much compared to its collateral.
This operation is accessible through MarginCallPrimaryFacet::flagShort, which checks through the onlyValidShortRecord modifier that the SR isn't Cancelled.
If the SR is valid, then its debt/collateral ratio is verified, and if it's below a specific threshold, flagged.
But that also means that if a SR is considered invalid, it cannot be flagged.
And it seems there is a way for the owner of a SR to cancel its SR while still holding the position.

The owner of a SR can mint an NFT to represent it and make it transferable.
This is done in 5 steps:
1) TransferFrom verifies usual stuff regarding the NFT (ownership, allowance, valid receiver...).
2) LibShortRecord::transferShortRecord is called.
3) transferShortRecord verifies that SR is not flagged nor Cancelled.
4) SR is deleted (setting its status to Cancelled).
5) a new SR is created with same parameters, but owned by the receiver.

Now, let's see what would happen if Alice has a SR_1 with a bad CR, and Bob tries to flag it.
Bob calls flagShort on SR_1, the tx is sent to the mempool.

Alice is watching the mempool, and doesn't want her SR to be flagged:
She front-runs Bob's tx with a transfer of her SR_1 to another of the addresses she controls.

Now Bob's tx will be executed after Alice's tx:
1) The SR_1 is "deleted" and its status set to Cancelled.
2) Bob's tx is executed, and flagShort reverts because of the onlyValidShortRecord.
3) Alice can do this trick again to keep her undercol SR until it can become dangerous.

But this is not over:
4) Even when her CR drops dangerously (CR<1.5), liquidateSecondary is also DoS'd as it has the same check for SR.Cancelled.

Because of this, a shorter could maintain the dangerous position (or multiple dangerous positions), while putting the protocol at risk.

## Proof of Concept

Add these tests to ERC721Facet.t.sol :

Front-running flag

```solidity
	function testauditfrontrunFlagShort() public {
		address alice = makeAddr("Alice"); //Alice will front-run Bob's attempt to flag her short
		address aliceSecondAddr = makeAddr("AliceSecondAddr");
		address bob = makeAddr("Bob"); //Bob will try to flag Alice's short 
		address randomUser = makeAddr("randomUser"); //regular user who created a bid order
		
		//A random user create a bid, Alice create a short, which will match with the user's bid
		fundLimitBidOpt(DEFAULTPRICE, DEFAULTAMOUNT, randomUser);
		fundLimitShortOpt(DEFAULTPRICE, DEFAULTAMOUNT, alice);
		//Alice then mint the NFT associated to the SR so that it can be transferred
		vm.prank(alice);
		diamond.mintNFT(asset, Constants.SHORTSTARTINGID);

		//ETH price drops from 4000 to 2666, making Alice's short flaggable because its < LibAsset.primaryLiquidationCR(asset)
		setETH(2666 ether);
		
		// Alice saw Bob attempt to flag her short, so she front-run him and transfer the SR
		vm.prank(alice);
		diamond.transferFrom(alice, aliceSecondAddr, 1);
		
		//Bob's attempt revert because the transfer of the short by Alice change the short status to SR.Cancelled
		vm.prank(bob);
		vm.expectRevert(Errors.InvalidShortId.selector);
		diamond.flagShort(asset, alice, Constants.SHORTSTARTINGID, Constants.HEAD);
	}	
```

Front-running liquidateSecondary

```solidity
    function testauditfrontrunPreventFlagAndSecondaryLiquidation() public {
		address alice = makeAddr("Alice"); //Alice will front-run Bob's attempt to flag her short
		address aliceSecondAddr = makeAddr("AliceSecondAddr");
		address aliceThirdAddr = makeAddr("AliceThirdAddr");
		address bob = makeAddr("Bob"); //Bob will try to flag Alice's short 
		address randomUser = makeAddr("randomUser"); //regular user who created a bid order
		
		//A random user create a bid, Alice create a short, which will match with the user's bid
        fundLimitBidOpt(DEFAULTPRICE, DEFAULTAMOUNT, randomUser);
		fundLimitShortOpt(DEFAULTPRICE, DEFAULTAMOUNT, alice);
		//Alice then mint the NFT associated to the SR so that it can be transferred
		vm.prank(alice);
        diamond.mintNFT(asset, Constants.SHORTSTARTINGID);

        //set cRatio below 1.1
        setETH(700 ether);
		
		//Alice is still blocking all attempts to flag her short by transferring it to her secondary address by front-running Bob
        vm.prank(alice);
        diamond.transferFrom(alice, aliceSecondAddr, 1);
		vm.prank(bob);
		vm.expectRevert(Errors.InvalidShortId.selector);
		diamond.flagShort(asset, alice, Constants.SHORTSTARTINGID, Constants.HEAD);

		//Alice  front-run (again...) Bob and transfers the NFT to a third address she owns
		vm.prank(aliceSecondAddr);
        diamond.transferFrom(aliceSecondAddr, aliceThirdAddr, 1);

		//Bob's try again on the new address, but its attempt revert because the transfer of the short by Alice change the short status to SR.Cancelled
		STypes.ShortRecord memory shortRecord = getShortRecord(aliceSecondAddr, Constants.SHORTSTARTINGID);
		depositUsd(bob, shortRecord.ercDebt);
        vm.expectRevert(Errors.MarginCallSecondaryNoValidShorts.selector);
		liquidateErcEscrowed(aliceSecondAddr, Constants.SHORTSTARTINGID, DEFAULT_AMOUNT, bob);
    }
```

## Recommendation

No data

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a front‑running race condition that allows the owner of a short position, represented as an NFT, to keep an under‑collateralised short open indefinitely. A Short Record (SR) stores the amount of collateral and debt for a short position and can be flagged as dangerous when its collateral‑to‑debt ratio (CR) falls below a protocol‑defined threshold. The flagShort and liquidateSecondary functions first verify that the SR is still valid by checking that its status is not Cancelled. When a user mints an NFT for an SR, the contract’s transferShortRecord routine is invoked during an NFT transfer. This routine deletes the original SR by setting its status to Cancelled and then creates a new SR with identical parameters but owned by the receiver. Because the validity check only looks at the Cancelled flag, any pending flagShort or liquidation call that was already in the mempool will revert after the NFT transfer, as the original SR no longer exists. An attacker can monitor the mempool, detect a liquidation or flagging transaction, and front‑run it by transferring the NFT to another address they control. The transfer cancels the SR, causing the subsequent flagShort or liquidateSecondary call to fail with an InvalidShortId or MarginCallSecondaryNoValidShorts error. By repeating this process, the attacker can maintain a dangerous short position (CR < 1.5) without ever being liquidated, effectively denying the protocol the ability to enforce its risk controls. The impact is that the protocol’s accounting assumptions are broken: positions that should be liquidated remain open, exposing the system to potential loss of collateral. This issue is observable from a user’s perspective as a short position that never gets flagged or liquidated despite a clearly low collateral ratio, leading to unexpected “nothing happens” behaviour when the protocol attempts to protect itself. The bug was discovered during an audit when tests were added that simulated mempool front‑running of flagShort and liquidateSecondary calls. It is hard to notice because the NFT transfer appears legitimate and the SR data is recreated, so standard state‑inspection tools see a valid short after the transfer. The root cause is the combination of tokenising positions as NFTs and an insufficient state transition check that allows the SR to be cancelled and recreated without updating the liquidation eligibility logic. To fix the issue, the contract should either prohibit transferring NFTs that represent under‑collateralised shorts, keep the original SR alive until any pending liquidation or flagging transaction is resolved, or modify the validity checks to consider the history of the SR rather than only the Cancelled flag. In generic terms, this is a race‑condition/front‑running vulnerability in a tokenised asset management system that breaks the enforcement of business rules governing collateral safety.
